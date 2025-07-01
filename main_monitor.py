import asyncio
import schedule
import os
from telethon import TelegramClient, events
from automacao_v3 import executar_automacao, TelegramSignalCollector
from analisador import analisar_sinal
from envio_resultado import enviar_telegram

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "29194173"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "aa6eac958b72727ff8802895a106a74c")
SESSION_NAME = "monitor_session"
GROUP_ID = int(os.getenv('TELEGRAM_GROUP_ID', '-1001673441581'))

async def rotina():
    print("[INFO] Executando rotina de análise e envio...")
    sinais = analisar_sinal()
    for sinal in sinais:
        ativo = sinal["ativo"]
        horario = sinal["horario"]
        score = sinal["score"]
        if score == 1:
            recomendacao = "✅ RECOMENDADO"
        elif score > 1:
            recomendacao = "✅ FORTEMENTE RECOMENDADO"
        elif score == 0:
            recomendacao = "🟡 MODERADO"
        else:
            recomendacao = "⚠️ NÃO RECOMENDADO"
        enviar_telegram(ativo, horario, recomendacao, score, ["Auto: critérios aplicados"], [])

async def main_loop():
    client = TelegramClient(SESSION_NAME, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.start()
    print("[INFO] Cliente Telegram iniciado.")

    # Inicia automação com o client centralizado
    await executar_automacao(client)

    # Opcional: inicia seu coletor com o client se precisar
    collector = TelegramSignalCollector(signals_to_collect=10, client=client)

    # Escuta mensagens novas
    @client.on(events.NewMessage(chats=GROUP_ID))
    async def handler(event):
        mensagem = event.raw_text
        if "direção" in mensagem.lower():
            print(f"[INFO] Mensagem com 'direção' detectada: {mensagem}")
            sinais = analisar_sinal()
            for sinal in sinais:
                ativo = sinal["ativo"]
                horario = sinal["horario"]
                score = sinal["score"]
                if score == 1:
                    recomendacao = "✅ RECOMENDADO"
                elif score > 1:
                    recomendacao = "✅ FORTEMENTE RECOMENDADO"
                elif score == 0:
                    recomendacao = "🟡 MODERADO"
                else:
                    recomendacao = "⚠️ NÃO RECOMENDADO"
                enviar_telegram(ativo, horario, recomendacao, score, ["Auto: critérios aplicados"], [])
        else:
            print(f"[INFO] Mensagem ignorada: {mensagem}")

    # Rotina periódica
    schedule.every(1).minutes.do(lambda: asyncio.create_task(rotina()))

    print("[INFO] Monitor iniciado. Rodando verificações a cada 1 minuto.")
    await client.run_until_disconnected()

def start_monitor():
    asyncio.run(main_loop())

if __name__ == "__main__":
    start_monitor()
