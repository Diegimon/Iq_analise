import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import gspread
import pytz
from google.oauth2.service_account import Credentials
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError

# === CONFIGURAÇÃO DE LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_signals.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# === DATACLASS PARA SINAIS ===
@dataclass
class Signal:
    horario: str
    ativo: str
    direcao: str
    resultado: str
    gale: int
    data: str = ""
    
    def to_list(self) -> List[str]:
        """Converte o sinal para lista para inserção na planilha"""
        return [self.data, self.horario, self.ativo, self.direcao, self.resultado, str(self.gale)]
    
    def get_key(self) -> Tuple[str, str]:
        """Retorna chave única para evitar duplicatas"""
        return (self.data, self.horario)

# === CLASSE PRINCIPAL ===
class TelegramSignalProcessor:
    def __init__(self):
        # Configurações do Telegram (usar variáveis de ambiente em produção)
        self.api_id = int(os.getenv('TELEGRAM_API_ID', '29194173'))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', 'aa6eac958b72727ff8802895a106a74c')
        self.session_name = 'sinais_session'
        self.group_id = int(os.getenv('TELEGRAM_GROUP_ID', '-1001673441581'))
        
        # Configurações do Google Sheets
        self.credentials_file = Path(os.getenv('GOOGLE_CREDENTIALS_FILE', 'uplifted-light-432518-k5-8d2823e4c54e.json'))
        self.sheet_name = os.getenv('SHEET_NAME', 'Trade')
        self.worksheet_name = os.getenv('WORKSHEET_NAME', 'Auto')
        
        # Configurações de processamento
        self.days_to_search = int(os.getenv('DAYS_TO_SEARCH', '30'))
        self.timezone = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '100'))
        
        # Padrão regex otimizado e compilado
        self.signal_pattern = re.compile(
            r'(✅|❌)(¹|²)?\s+([A-Z0-9\-]+)\s+-\s+(\d{2}:\d{2}:\d{2})\s+-\s+M1\s+-\s+(put|call)\s+-\s+(WIN|LOSS)',
            re.IGNORECASE
        )
        
        # Mapeamentos para melhor performance
        self.result_map = {'✅': 'WIN', '❌': 'LOSS'}
        self.gale_map = {'¹': 1, '²': 2}
        
        self.client: Optional[TelegramClient] = None
        self.worksheet = None
        
    async def __aenter__(self):
        """Context manager para inicialização assíncrona"""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager para limpeza"""
        await self.cleanup()
        
    async def initialize(self):
        """Inicializa o cliente Telegram e a conexão com Google Sheets"""
        try:
            # Inicializar cliente Telegram
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start()
            logger.info("Cliente Telegram inicializado com sucesso")
            
            # Inicializar Google Sheets
            await self._initialize_sheets()
            logger.info("Google Sheets inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            raise
            
    async def _initialize_sheets(self):
        """Inicializa conexão com Google Sheets de forma assíncrona"""
        def _sync_sheets_init():
            if not self.credentials_file.exists():
                raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {self.credentials_file}")
                
            # Usar google.oauth2 ao invés de oauth2client (depreciado)
            scope = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            
            credentials = Credentials.from_service_account_file(
                str(self.credentials_file), 
                scopes=scope
            )
            
            gc = gspread.authorize(credentials)
            sheet = gc.open(self.sheet_name)
            return sheet.worksheet(self.worksheet_name)
        
        # Executar operação síncrona em thread separada
        loop = asyncio.get_event_loop()
        self.worksheet = await loop.run_in_executor(None, _sync_sheets_init)
        
    async def cleanup(self):
        """Limpa recursos"""
        if self.client:
            await self.client.disconnect()
            logger.info("Cliente Telegram desconectado")
            
    def parse_signal(self, text: str) -> Optional[Signal]:
        """
        Extrai dados do sinal da mensagem
        
        Args:
            text: Texto da mensagem
            
        Returns:
            Signal object ou None se não encontrar padrão
        """
        if not text:
            return None
            
        match = self.signal_pattern.search(text)
        if not match:
            return None
            
        try:
            simbolo_resultado, gale_symbol, ativo, horario, direcao, status = match.groups()
            
            resultado = self.result_map.get(simbolo_resultado, 'UNKNOWN')
            gale_valor = self.gale_map.get(gale_symbol, 0)
            
            return Signal(
                horario=horario,
                ativo=ativo.upper(),
                direcao=direcao.upper(),
                resultado=resultado,
                gale=gale_valor
            )
            
        except Exception as e:
            logger.warning(f"Erro ao fazer parse do sinal: {e}")
            return None
            
    async def get_existing_records(self) -> Set[Tuple[str, str]]:
        """
        Obtém registros existentes da planilha de forma assíncrona
        
        Returns:
            Set com chaves (data, horario) dos registros existentes
        """
        def _get_records():
            try:
                records = self.worksheet.get_all_values()
                # Pular cabeçalho se existir e não estiver vazio
                if records and records[0] and any(cell.strip() for cell in records[0] if cell):
                    # Verificar se parece com cabeçalho (contém texto não-numérico)
                    first_row = records[0]
                    if any(not cell.replace('/', '').replace(':', '').replace('-', '').isdigit() 
                           for cell in first_row[:2] if cell.strip()):
                        records = records[1:]
                return records
            except Exception as e:
                logger.error(f"Erro ao obter registros existentes: {e}")
                return []
        
        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(None, _get_records)
        
        existing_keys = set()
        for row in records:
            if len(row) >= 2 and row[0] and row[1]:
                # Limpar dados e validar formato
                data = row[0].strip()
                horario = row[1].strip()
                if data and horario:
                    existing_keys.add((data, horario))
                    
        logger.info(f"Encontrados {len(existing_keys)} registros existentes na planilha")
        return existing_keys
        
    def is_trading_day(self, date: datetime) -> bool:
        """
        Verifica se é um dia útil de trading
        
        Args:
            date: Data para verificar
            
        Returns:
            True se for dia útil (seg-sex)
        """
        # 0=segunda, 6=domingo
        return date.weekday() < 5
        
    async def fetch_messages(self, start_date: datetime, end_date: datetime) -> List[Signal]:
        """
        Busca TODAS as mensagens do Telegram no período especificado
        Garante que todos os sinais sejam coletados, independente da planilha
        
        Args:
            start_date: Data de início
            end_date: Data de fim
            
        Returns:
            Lista de TODOS os sinais processados (sem duplicatas internas)
        """
        signals = []
        processed_messages = 0
        found_signals = 0
        
        # Set para controlar duplicatas dentro da mesma execução
        seen_signals = set()
        # Set para controlar mensagens já processadas (por ID)
        seen_messages = set()
        
        logger.info(f"🔍 Iniciando coleta completa de sinais do período...")
        
        try:
            async for message in self.client.iter_messages(
                self.group_id, 
                min_date=start_date, 
                max_date=end_date,
                limit=None
            ):
                # Verificar se já processamos esta mensagem
                if message.id in seen_messages:
                    continue
                seen_messages.add(message.id)
                processed_messages += 1
                
                # Verificar se a mensagem está no período correto
                message_date = message.date.astimezone(self.timezone)
                
                if message_date < start_date:
                    logger.debug(f"Mensagem anterior ao período: {message_date}")
                    break
                    
                if message_date > end_date:
                    continue
                    
                # Ignorar finais de semana
                if not self.is_trading_day(message_date):
                    continue
                    
                if message.message:
                    signal = self.parse_signal(message.message)
                    if signal:
                        signal.data = message_date.strftime("%d/%m/%Y")
                        signal_key = signal.get_key()
                        
                        # Verificar duplicata dentro da execução atual
                        if signal_key not in seen_signals:
                            seen_signals.add(signal_key)
                            signals.append(signal)
                            found_signals += 1
                            
                            logger.debug(f"✅ Sinal coletado: {signal.data} {signal.horario} {signal.ativo} {signal.resultado}")
                        else:
                            logger.debug(f"⚠️ Sinal duplicado na execução: {signal_key}")
                            
                # Log de progresso a cada 100 mensagens processadas
                if processed_messages % 100 == 0:
                    logger.info(f"📊 Processadas {processed_messages} mensagens, encontrados {found_signals} sinais únicos...")
                            
        except FloodWaitError as e:
            logger.warning(f"⏱️ Rate limit atingido. Aguardando {e.seconds} segundos...")
            await asyncio.sleep(e.seconds)
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar mensagens: {e}")
            
        duplicates_in_execution = processed_messages - found_signals
        logger.info(f"📈 COLETA CONCLUÍDA:")
        logger.info(f"   • Mensagens processadas: {processed_messages}")
        logger.info(f"   • Sinais únicos coletados: {found_signals}")
        logger.info(f"   • Mensagens sem sinais/duplicatas: {duplicates_in_execution}")
        
        return signals
        
    async def save_signals_batch(self, signals: List[Signal]) -> bool:
        """
        Salva sinais na planilha em lotes para melhor performance
        
        Args:
            signals: Lista de sinais para salvar
            
        Returns:
            True se salvou com sucesso
        """
        if not signals:
            logger.info("ℹ️ Nenhum sinal para salvar")
            return True
            
        def _save_batch(data_to_save):
            try:
                self.worksheet.append_rows(data_to_save, value_input_option='RAW')
                return True
            except Exception as e:
                logger.error(f"❌ Erro ao salvar lote: {e}")
                return False
                
        # Converter sinais para formato da planilha
        data_to_save = [signal.to_list() for signal in signals]
        
        logger.info(f"💾 Salvando {len(data_to_save)} sinais em lotes de {self.batch_size}...")
        
        # Salvar em lotes para melhor performance
        loop = asyncio.get_event_loop()
        total_saved = 0
        
        for i in range(0, len(data_to_save), self.batch_size):
            batch = data_to_save[i:i + self.batch_size]
            batch_num = i//self.batch_size + 1
            total_batches = (len(data_to_save) + self.batch_size - 1) // self.batch_size
            
            logger.info(f"📦 Salvando lote {batch_num}/{total_batches} ({len(batch)} sinais)...")
            
            success = await loop.run_in_executor(None, _save_batch, batch)
            
            if not success:
                logger.error(f"❌ Falha ao salvar lote {batch_num}")
                return False
                
            total_saved += len(batch)
            logger.info(f"✅ Lote {batch_num} salvo com sucesso! Total salvo: {total_saved}/{len(data_to_save)}")
            
            # Pequena pausa para evitar rate limits
            if i + self.batch_size < len(data_to_save):  # Não pausar no último lote
                await asyncio.sleep(0.5)
        
        logger.info(f"🎉 TODOS OS SINAIS SALVOS COM SUCESSO! Total: {total_saved}")
        return True
        
    async def process_signals(self) -> Dict[str, Any]:
        """
        Função principal para processar sinais
        SEMPRE coleta todos os sinais do período e salva apenas os novos
        
        Returns:
            Dicionário com estatísticas do processamento
        """
        # Calcular período de busca (últimos 30 dias por padrão)
        now = datetime.now(self.timezone)
        start_date = (now - timedelta(days=self.days_to_search)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date = now
        
        logger.info(f"🚀 INICIANDO PROCESSAMENTO COMPLETO")
        logger.info(f"📅 Período: {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')} ({self.days_to_search} dias)")
        logger.info(f"🎯 Grupo Telegram ID: {self.group_id}")
        
        # PASSO 1: Coletar TODOS os sinais do período (independente da planilha)
        logger.info(f"🔍 PASSO 1: Coletando TODOS os sinais do período...")
        all_signals = await self.fetch_messages(start_date, end_date)
        
        if not all_signals:
            logger.warning("⚠️ Nenhum sinal encontrado no período especificado!")
            return {
                'total_found': 0,
                'new_signals': 0,
                'duplicates_in_sheet': 0,
                'saved_successfully': True,
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat()
            }
        
        # PASSO 2: Verificar o que já existe na planilha
        logger.info(f"📊 PASSO 2: Verificando registros existentes na planilha...")
        existing_keys = await self.get_existing_records()
        
        # PASSO 3: Filtrar apenas os sinais novos para salvar
        logger.info(f"🔄 PASSO 3: Filtrando sinais novos...")
        new_signals = []
        duplicates_from_sheet = 0
        
        for signal in all_signals:
            signal_key = signal.get_key()
            if signal_key not in existing_keys:
                new_signals.append(signal)
                existing_keys.add(signal_key)  # Adicionar para evitar duplicatas futuras nesta execução
            else:
                duplicates_from_sheet += 1
                logger.debug(f"📝 Sinal já existe na planilha: {signal_key}")
        
        # PASSO 4: Salvar os sinais novos
        success = False
        if new_signals:
            logger.info(f"💾 PASSO 4: Salvando {len(new_signals)} sinais novos na planilha...")
            success = await self.save_signals_batch(new_signals)
        else:
            logger.info(f"ℹ️ PASSO 4: Nenhum sinal novo para salvar (todos já existem na planilha)")
            success = True  # Não há erro se não há novos sinais
                
        # ESTATÍSTICAS FINAIS
        logger.info(f"📈 ESTATÍSTICAS FINAIS:")
        logger.info(f"   • Total de sinais coletados: {len(all_signals)}")
        logger.info(f"   • Sinais novos salvos: {len(new_signals)}")
        logger.info(f"   • Sinais já existentes: {duplicates_from_sheet}")
        logger.info(f"   • Operação bem-sucedida: {'✅ SIM' if success else '❌ NÃO'}")
        
        return {
            'total_found': len(all_signals),
            'new_signals': len(new_signals),
            'duplicates_in_sheet': duplicates_from_sheet,
            'saved_successfully': success,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat()
        }

# === FUNÇÃO PRINCIPAL ===
async def main():
    """Função principal assíncrona"""
    try:
        async with TelegramSignalProcessor() as processor:
            stats = await processor.process_signals()
            
            logger.info("=== RESUMO DO PROCESSAMENTO ===")
            logger.info(f"Período: {stats['period_start']} até {stats['period_end']}")
            logger.info(f"Total encontrado: {stats['total_found']}")
            logger.info(f"Novos sinais: {stats['new_signals']}")
            logger.info(f"Duplicados da planilha: {stats['duplicates_in_sheet']}")
            logger.info(f"Salvos com sucesso: {stats['saved_successfully']}")
            
            if stats['saved_successfully'] and stats['new_signals'] > 0:
                logger.info("✅ Processamento concluído com sucesso!")
            elif stats['new_signals'] == 0:
                logger.info("ℹ️ Nenhum sinal novo encontrado no período.")
            else:
                logger.error("❌ Erro ao salvar os sinais!")
                
    except KeyboardInterrupt:
        logger.info("Processamento interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro durante o processamento: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())