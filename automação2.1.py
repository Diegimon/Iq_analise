import asyncio
import logging
import os
import re
from datetime import datetime
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path
import gspread
import pytz
from google.oauth2.service_account import Credentials
from telethon import TelegramClient

# === CONFIG LOGGING ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === DATA MODEL ===
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
    def __init__(self, signals_to_collect: int):
        self.api_id = int(os.getenv('TELEGRAM_API_ID', '29194173'))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', 'aa6eac958b72727ff8802895a106a74c')
        self.session_name = 'sinais_session'
        self.group_id = int(os.getenv('TELEGRAM_GROUP_ID', '-1001673441581'))
        
        self.credentials_file = Path(os.getenv('GOOGLE_CREDENTIALS_FILE', 'uplifted-light-432518-k5-8d2823e4c54e.json'))
        self.sheet_name = os.getenv('SHEET_NAME', 'Trade')
        self.worksheet_name = os.getenv('WORKSHEET_NAME', 'Auto')
        
        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))
        self.timezone = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))
        
        self.signals_to_collect = signals_to_collect
        self.total_messages_to_fetch = self.signals_to_collect * 2

        self.signal_pattern = re.compile(
            r'(✅|❌)(¹|²)?\s+([A-Z0-9\-]+)\s+-\s+(\d{2}:\d{2}:\d{2})\s+-\s+M1\s+-\s+(put|call)\s+-\s+(WIN|LOSS)',
            re.IGNORECASE
        )
        self.result_map = {'✅': 'WIN', '❌': 'LOSS'}
        self.gale_map = {'¹': 1, '²': 2}
        
        self.client: Optional[TelegramClient] = None
        self.worksheet = None

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def initialize(self):
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start()
        logger.info("Cliente Telegram conectado com sucesso.")
        await self._initialize_sheets()

    async def _initialize_sheets(self):
        def _sheets():
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.readonly']
            credentials = Credentials.from_service_account_file(str(self.credentials_file), scopes=scope)
            gc = gspread.authorize(credentials)
            sheet = gc.open(self.sheet_name)
            return sheet.worksheet(self.worksheet_name)
        loop = asyncio.get_event_loop()
        self.worksheet = await loop.run_in_executor(None, _sheets)

    async def cleanup(self):
        if self.client:
            await self.client.disconnect()
            logger.info("Cliente Telegram desconectado.")

    def parse_signal(self, text: str) -> Optional[Signal]:
        match = self.signal_pattern.search(text)
        if not match:
            return None
        try:
            simbolo_resultado, gale_symbol, ativo, horario, direcao, status = match.groups()
            resultado = self.result_map.get(simbolo_resultado, 'UNKNOWN')
            gale_valor = self.gale_map.get(gale_symbol, 0)
            return Signal(horario=horario, ativo=ativo.upper(), direcao=direcao.upper(), resultado=resultado, gale=gale_valor)
        except:
            return None

    async def collect_signals(self):
        logger.info(f"Buscando as últimas {self.total_messages_to_fetch} mensagens...")
        signals = []
        seen_signals = set()
        async for message in self.client.iter_messages(self.group_id, limit=self.total_messages_to_fetch):
            message_date = message.date.astimezone(self.timezone)
            if message.message:
                signal = self.parse_signal(message.message)
                if signal:
                    signal.data = message_date.strftime("%d/%m/%Y")
                    key = signal.get_key()
                    if key not in seen_signals:
                        seen_signals.add(key)
                        signals.append(signal)
        logger.info(f"Total de sinais válidos encontrados: {len(signals)}")
        return signals

    async def save_signals(self, signals: List[Signal]):
        if not signals:
            logger.info("Nenhum sinal para salvar.")
            return

        def _save(batch):
            # Descobrir a próxima linha vazia na coluna A
            values = self.worksheet.col_values(1)
            next_row = len(values) + 1

            # Inserir o batch a partir da próxima linha vazia, respeitando A-G
            self.worksheet.update(f"A{next_row}:G{next_row + len(batch) - 1}", batch)

        data = [s.to_list() for s in signals]
        loop = asyncio.get_event_loop()
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i+self.batch_size]
            await loop.run_in_executor(None, _save, batch)
            logger.info(f"Salvo batch de {len(batch)} sinais na posição correta.")
            await asyncio.sleep(0.5)


async def main():
    qtde = int(input("Quantos resultados você deseja buscar? "))
    async with TelegramSignalCollector(qtde) as collector:
        signals = await collector.collect_signals()
        await collector.save_signals(signals)

if __name__ == '__main__':
    asyncio.run(main())