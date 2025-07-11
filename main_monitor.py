import asyncio
import os
from telethon import TelegramClient, events
from automacao_v3 import executar_automacao, TelegramSignalCollector, enviar_ultimo_sinal_da_planilha
from analisador import analisar_sinal,coletar_dados
from envio_resultado import enviar_telegram
from calendário import main as executar_calendario  # IMPORTA O MAIN DO CALENDÁRIO

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "29194173"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "aa6eac958b72727ff8802895a106a74c")
SESSION_NAME = "monitor_session"
GROUP_ID = int(os.getenv('TELEGRAM_GROUP_ID', '-1001673441581'))

async def main_loop():
    client = TelegramClient(SESSION_NAME, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.start()
    print("[INFO] Cliente Telegram iniciado.")

    # Executa calendário no início
    await asyncio.to_thread(verificar_e_executar_calendario)

    # Executa automação no início
    print("[INFO] Gravando ultimos sinais na aba auto")
    await executar_automacao(client)
    print("[INFO] Monitorando novas mensagens")

    @client.on(events.NewMessage(chats=GROUP_ID))
    async def handler(event):
        mensagem = event.raw_text
        if "direção" in mensagem.lower():
            print(f"[INFO] Mensagem com 'direção' detectada: {mensagem}")

            collector = TelegramSignalCollector(500, client)
            sinal_obj = collector.parse_signal(mensagem)

            if sinal_obj:
                ativo = sinal_obj.ativo
                horario = sinal_obj.horario

                # Carregar os dados coletados reais do calendário (ou planilha)
                dados_coletados = coletar_dados()
                if dados_coletados:  
                    print("[INFO] Informações de ativos e horarios coletados da planilha")
                    sinais = analisar_sinal(ativo, horario, dados_coletados)
                    for r in sinais:
                        print(f"[INFO] Enviando sinal - NOVO para o telegram")
                        enviar_telegram(
                            r["ativo"],
                            r["horario"],
                            r["winrate_horario"],
                            r["direcao"],
                            r["winrate_ativo"],
                            r["recomendacao"],
                            r["score"],
                            r["criterios"],
                            r["noticias_proximas"]
                        )

                    # Agenda nova automação em 6 min
                    asyncio.create_task(agendar_automacao_em_6_min(client))
                else:
                    print("[WARN] Não foi possível extrair o sinal da mensagem.")
            else:
                print(f"[INFO] Mensagem ignorada: {mensagem}")

    await client.run_until_disconnected()

async def agendar_automacao_em_6_min(client):
    print("[INFO] Coleta de sinais agendada para rodar em 6 minutos...")
    await asyncio.sleep(360)
    print("[INFO] Verificando calendário pós sinal")
    await asyncio.to_thread(verificar_e_executar_calendario)

    # Executa automação no início
    print("[INFO] Gravando ultimos sinais na aba auto...")
    await executar_automacao(client)
    print("[INFO] Analisando ultimo sinal gravado...")
    await enviar_ultimo_sinal_da_planilha()
    print("[INFO] Coleta de sinais executada!")
    print("[INFO] Monitorando novas mensagens...")
    


from datetime import datetime

def verificar_e_executar_calendario():
    caminho_arquivo = "ultima_execucao.txt"
    hoje = datetime.now().strftime("%d/%m/%Y")
    data_ultima_execucao = ""

    if os.path.exists(caminho_arquivo):
        with open("ultima_execucao.txt", "r") as f:
            data_ultima_execucao = f.readline().strip()

    if data_ultima_execucao == hoje:
        print(f"[INFO] Calendário já atualizado hoje ({hoje}). Nenhuma ação necessária.")
        return
    else:
        print(f"Data da ultima ex `{data_ultima_execucao} e \n hoje: {hoje}")
        print(f"[INFO] Executando calendário (última execução: {data_ultima_execucao})...")
        executar_calendario()  # chama a função real do calendário

        # Atualiza o arquivo com a data atual
        with open(caminho_arquivo, "w") as f:
            f.write(hoje)
        print(f"[INFO] Data da última execução atualizada para {hoje}.")


def start_monitor():
    asyncio.run(main_loop())

if __name__ == "__main__":
    start_monitor()
