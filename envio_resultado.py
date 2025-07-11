import requests

TOKEN = "7604694082:AAHDPs8kA7JH0-k7dyOgHY7TbY9nWHQRbI4"
CHAT_ID = "6064424580"

def enviar_telegram(ativo, horario,winrate_horario,direcao,winrate_ativo, recomendacao, score, criterios, noticias_proximas):
    if direcao == "put" or "PUT":
        direcao = "PUT 🔻"
    else:
        direcao = "CALL 🟢 "
    mensagem = f"""📈 NOVO SINAL ANALISADO

Ativo: {ativo} Winrate {winrate_ativo}%
Horário: {horario} Winrate: {winrate_horario}%
Direção: {direcao}
Recomendação: {recomendacao}
Score: {score}

Critérios:
{'\n- '.join(criterios)}

Notícias:
{'\n- '.join(noticias_proximas)}
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": mensagem})