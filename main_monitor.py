import os
import asyncio
import logging
from calendário import main as atualizar_calendario
from telethon import TelegramClient, events
from subprocess import run
from datetime import datetime
from calendário import main as atualizar_calendario

# === CONFIG ===
API_ID = int(os.getenv("TELEGRAM_API_ID", "29194173"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "aa6eac958b72727ff8802895a106a74c")
GRUPO_ID = int(os.getenv("TELEGRAM_GROUP_ID", "-1001673441581"))
SESSION_NAME = "monitor_runner"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("log_monitor.txt", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
ULTIMO_SINAL = "sinal.txt"


def atualizar_calendario_se_necessario():
    caminho = "ultima_atualizacao_calendario.txt"
    hoje = datetime.now().strftime("%Y-%m-%d")

    if os.path.exists(caminho):
        with open(caminho, "r") as f:
            ultima_data = f.read().strip()
            if ultima_data == hoje:
                logging.info("📅 Calendário já foi atualizado hoje.")
                return

    logging.info("📅 Atualizando calendário de notícias...")
    atualizar_calendario()
    with open(caminho, "w") as f:
        f.write(hoje)

def carregar_ultimo_sinal():
    if not os.path.exists(ULTIMO_SINAL):
        return None, None
    with open(ULTIMO_SINAL, "r") as f:
        partes = f.read().strip().split("|")
        return partes[0], partes[1] if len(partes) == 2 else (None, None)

@client.on(events.NewMessage(chats=GRUPO_ID))
async def nova_mensagem(event):


    texto = event.raw_text.strip()
    if not texto:
        return

    # Simples checagem: só roda automação se for diferente do último processado
    ativo_atual, horario_atual = carregar_ultimo_sinal()
    if ativo_atual and horario_atual:
        if ativo_atual in texto and horario_atual in texto:
            logging.info("⚠️ Sinal repetido. Ignorando.")
            return

    logging.info("🟢 Nova mensagem detectada. Executando automação_v3.py")
    run(["python", "automação_v3.py"], shell=True)

async def main():
    atualizar_calendario_se_necessario()
    await client.start()
    logging.info("🎯 Runner iniciado. Monitorando mensagens no grupo...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
