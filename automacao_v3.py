import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path
import gspread
import pytz
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class Signal:
    horario: str
    ativo: str
    direcao: str
    resultado: str
    gale: int
    data: str = ""

    def to_list(self) -> List[str]:
        return [self.data, self.horario, self.ativo, self.direcao, self.resultado, str(self.gale)]

    def get_key(self) -> Tuple[str, str]:
        return (self.data, self.horario)

class TelegramSignalCollector:
    def __init__(self, signals_to_collect: int, client):
        self.client = client
        self.group_id = int(os.getenv('TELEGRAM_GROUP_ID', '-1001673441581'))

        self.credentials_file = Path(os.getenv('GOOGLE_CREDENTIALS_FILE', 'uplifted-light-432518-k5-8d2823e4c54e.json'))
        self.sheet_name = os.getenv('SHEET_NAME', 'Trade')
        self.worksheet_name = os.getenv('WORKSHEET_NAME', 'Auto')

        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))
        self.timezone = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))

        self.signals_to_collect = signals_to_collect
        self.total_messages_to_fetch = self.signals_to_collect * 2

        self.signal_pattern = re.compile(
            r'(?:✅|❌)?(?:¹|²)?[\s\S]*?(?:Ativo:\s*([A-Z0-9\-]+)[\s\S]*?Horário:\s*(\d{2}:\d{2}:\d{2})[\s\S]*?Direção:\s*(call|put)'
            r'|([A-Z0-9\-]+)\s*-\s*(\d{2}:\d{2}:\d{2})\s*-\s*M1\s*-\s*(call|put)\s*-\s*(WIN|LOSS))',
            re.IGNORECASE
        )
        self.worksheet = None

    async def initialize_sheets(self):
        def _sheets():
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.readonly']
            credentials = Credentials.from_service_account_file(str(self.credentials_file), scopes=scope)
            gc = gspread.authorize(credentials)
            sheet = gc.open(self.sheet_name)
            return sheet.worksheet(self.worksheet_name)
        loop = asyncio.get_event_loop()
        self.worksheet = await loop.run_in_executor(None, _sheets)

    def parse_signal(self, text: str) -> Optional[Signal]:
        match = self.signal_pattern.search(text)
        if not match:
            return None
        try:
            if match.group(1):
                ativo, horario, direcao = match.group(1), match.group(2), match.group(3)
                gale = 0
                if '¹' in text:
                    gale = 1
                elif '²' in text:
                    gale = 2
                return Signal(horario=horario.strip(), ativo=ativo.strip().upper(), direcao=direcao.strip().upper(), resultado="PENDENTE", gale=gale)
            elif match.group(4):
                ativo, horario, direcao, resultado = match.group(4), match.group(5), match.group(6), match.group(7)
                gale = 0
                if '¹' in text:
                    gale = 1
                elif '²' in text:
                    gale = 2
                return Signal(horario=horario.strip(), ativo=ativo.strip().upper(), direcao=direcao.strip().upper(), resultado=resultado.strip().upper(), gale=gale)
        except Exception as e:
            logger.error(f"Erro ao interpretar sinal: {e}")
            return None


    async def collect_and_save(self):
        await self.initialize_sheets()
        logger.info(f"Buscando as últimas {self.total_messages_to_fetch} mensagens...")
        signals = []
        seen_signals = set()
        async for message in self.client.iter_messages(self.group_id, limit=self.total_messages_to_fetch):
            message_date = message.date.astimezone(self.timezone)
            if message.message:
                signal = self.parse_signal(message.message)
                if signal and signal.resultado.upper() in ("WIN", "LOSS"):
                    try:
                        signal_hour = datetime.strptime(signal.horario, "%H:%M:%S").time()
                        msg_hour = message_date.time()
                        if signal_hour > msg_hour:
                            signal.data = (message_date - timedelta(days=1)).strftime("%d/%m/%Y")
                        else:
                            signal.data = message_date.strftime("%d/%m/%Y")
                    except Exception as e:
                        logger.error(f"Erro ao ajustar data do sinal: {e}")
                        signal.data = message_date.strftime("%d/%m/%Y")
                    key = signal.get_key()
                    if key not in seen_signals:
                        seen_signals.add(key)
                        signals.append(signal)
        logger.info(f"Total de sinais válidos encontrados (WIN/LOSS): {len(signals)}")
        await self.save_signals(signals)
        await self.clean_old_records()

    async def save_signals(self, signals: List[Signal]):
        if not signals:
            logger.info("Nenhum sinal novo para salvar.")
            return

        def _load_existing_with_index():
            values = self.worksheet.get_all_values()
            return [(i + 1, row) for i, row in enumerate(values[2:], start=3) if len(row) >= 5]

        def _update_cell(row_number: int, signal: Signal):
            self.worksheet.update(f"A{row_number}:G{row_number}", [signal.to_list()])
            logger.info(f"Linha {row_number} atualizada com novo resultado: {signal.resultado}")

        def _append_batch(batch):
            values = self.worksheet.col_values(1)
            next_row = len(values) + 1
            self.worksheet.update(f"A{next_row}:G{next_row + len(batch) - 1}", batch)
            logger.info(f"Salvo lote de {len(batch)} novos sinais.")

        loop = asyncio.get_running_loop()
        existing_with_index = await loop.run_in_executor(None, _load_existing_with_index)

        batch_to_append = []
        for signal in signals:
            found = False
            for idx, row in existing_with_index:
                if row[0] == signal.data and row[1] == signal.horario:
                    if row[4].upper() == "PENDENTE" and signal.resultado.upper() in ("WIN", "LOSS"):
                        await loop.run_in_executor(None, _update_cell, idx, signal)
                    found = True
                    break
            if not found:
                batch_to_append.append(signal.to_list())

        if batch_to_append:
            for i in range(0, len(batch_to_append), self.batch_size):
                batch = batch_to_append[i:i + self.batch_size]
                await loop.run_in_executor(None, _append_batch, batch)
                await asyncio.sleep(0.5)

    async def clean_old_records(self):
        logger.info("Verificando necessidade de limpeza de registros antigos...")
        values = self.worksheet.get_all_values()
        if len(values) > 502:
            header = values[:2]
            rows_to_keep = values[-500:]
            rows_to_keep = [row[:7] for row in rows_to_keep]
            self.worksheet.clear()
            self.worksheet.update("A1:G2", header)
            self.worksheet.update(f"A3:G{2 + len(rows_to_keep)}", rows_to_keep)
            logger.info(f"Limpeza realizada. Total mantido (fora cabeçalho): {len(rows_to_keep)}")
        else:
            logger.info("Nenhuma limpeza necessária.")



async def executar_automacao(telegram_client):
    collector = TelegramSignalCollector(500, telegram_client)
    await collector.collect_and_save()
