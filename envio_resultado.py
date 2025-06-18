import requests

TOKEN = "7604694082:AAHDPs8kA7JH0-k7dyOgHY7TbY9nWHQRbI4"
CHAT_ID = "6064424580"

def enviar_telegram(ativo, horario, recomendacao, score, motivos, noticias):
    mensagem = f"""📈 NOVO SINAL ANALISADO

Ativo: {ativo}
Horário: {horario}
Recomendação: {recomendacao}
Score: {score}

Critérios:
- {'\n- '.join(motivos)}

Notícias:
- {'\n- '.join([f"{n[1]} - {n[2]} (impacto {n[3]})" for n in noticias]) if noticias else "Nenhuma notícia próxima."}
"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": mensagem})
