import gspread
from google.oauth2.service_account import Credentials

CREDENTIALS_FILE = 'uplifted-light-432518-k5-8d2823e4c54e.json'
SHEET_NAME = 'Trade'

def coletar_dados():
    # Conectar ao Google Sheets
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.readonly']
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
    gc = gspread.authorize(creds)

    # Abrir planilha
    sheet = gc.open(SHEET_NAME)
    aba_analise = sheet.worksheet("ANALISES")
    aba_noticias = sheet.worksheet("NOTICIAS")

    # Coletar melhores ativos
    melhores = aba_analise.get("J20:J22")
    melhores_ativos = [linha[0].strip().upper() for linha in melhores if linha and linha[0]]

    # Coletar piores ativos
    piores = aba_analise.get("O20:O22")
    piores_ativos = [linha[0].strip().upper() for linha in piores if linha and linha[0]]

    # Coletar horários e winrates
    linhas = aba_analise.get("A2:B26")
    horarios_info = []
    for linha in linhas:
        if len(linha) < 2:
            continue
        horario = linha[0].strip()
        winrate_raw = linha[1].replace("%", "").replace(",", ".").strip()
        try:
            winrate = float(winrate_raw)
            horarios_info.append({
                "horario": horario,
                "winrate": winrate
            })
        except:
            print(f"❌ Ignorado horário '{horario}': winrate inválido '{linha[1]}'")
            continue

    # Coletar notícias
    noticias_lidas = []
    noticias = aba_noticias.get_all_values()[1:]  # Ignora cabeçalho
    for n in noticias:
        horario = n[0].strip() if len(n) > 0 else ""
        moeda = n[1].strip() if len(n) > 1 else ""
        impacto = n[2].strip() if len(n) > 2 else ""
        noticia = n[3].strip() if len(n) > 3 else ""
        noticias_lidas.append({
            "horario": horario,
            "moeda": moeda,
            "impacto": impacto,
            "noticia": noticia
        })

    # Printar dados coletados
    print("✅ MELHORES ATIVOS:")
    for ativo in melhores_ativos:
        print(f"- {ativo}")

    print("\n⚠ PIORES ATIVOS:")
    for ativo in piores_ativos:
        print(f"- {ativo}")

    print("\n⚠ HORÁRIOS RUINS (winrate < 85%):")
    for h in horarios_info:
        if h["winrate"] < 85.0:
            print(f"- {h['horario']}: {h['winrate']:.2f}%")

    print(f"\n📰 TOTAL DE NOTÍCIAS OBTIDAS: {len(noticias_lidas)}")

    return {
        "melhores_ativos": melhores_ativos,
        "piores_ativos": piores_ativos,
        "horarios_info": horarios_info,
        "noticias": noticias_lidas
    }
from datetime import datetime, timedelta

from datetime import datetime

def analisar_sinal(ativo, horario_str, dados_coletados):
    score = 0
    ativo = ativo.strip().upper()
    try:
        horario_sinal = datetime.strptime(horario_str, "%H:%M:%S")
    except:
        print(f"❌ Erro: Horário do sinal inválido '{horario_str}'")
        return score

    melhores_ativos = dados_coletados["melhores_ativos"]
    piores_ativos = dados_coletados["piores_ativos"]
    horarios_info = dados_coletados["horarios_info"]
    noticias = dados_coletados["noticias"]

    # Avaliar ativo
    if ativo in piores_ativos:
        score -= 1
        print(f"⚠ Ativo '{ativo}' está entre os piores: -1")
    elif ativo in melhores_ativos:
        score += 1
        print(f"✅ Ativo '{ativo}' está entre os melhores: +1")

    # Avaliar horário ruim
    piores_horarios = [h["horario"] for h in horarios_info if h["winrate"] < 80.0]
    if any(horario_sinal.strftime("%H:%M") == h for h in piores_horarios):
        score -= 1
        print(f"⚠ Horário '{horario_sinal.strftime('%H:%M')}' está entre os piores: -1")
    else:
        if ativo in melhores_ativos:
            score += 1
            print(f"✅ Ativo bom e horário não ruim: +1")

    # Avaliar notícias
    maior_impacto_atingindo = 0
    noticia_impacto = None
    noticia_passada = None
    noticia_futura = None
    menor_delta_passado = None
    menor_delta_futuro = None

    for n in noticias:
        try:
            noticia_hora = datetime.strptime(n["horario"], "%H:%M")
            impacto = int(n["impacto"])
            delta_min = (horario_sinal - noticia_hora).total_seconds() / 60

            # Última notícia passada
            if delta_min >= 0:
                if menor_delta_passado is None or delta_min < menor_delta_passado:
                    menor_delta_passado = delta_min
                    noticia_passada = n
            # Próxima notícia futura
            else:
                delta_min = abs(delta_min)
                if menor_delta_futuro is None or delta_min < menor_delta_futuro:
                    menor_delta_futuro = delta_min
                    noticia_futura = n

            delta = abs((horario_sinal - noticia_hora).total_seconds()) / 60

            # Avaliar impacto
            if impacto == 1 and delta <= 10:
                if maior_impacto_atingindo < 1:
                    maior_impacto_atingindo = 1
                    noticia_impacto = n
            elif impacto == 2 and delta <= 30:
                if maior_impacto_atingindo < 2:
                    maior_impacto_atingindo = 2
                    noticia_impacto = n
            elif impacto == 3 and delta <= 60:
                if maior_impacto_atingindo < 3:
                    maior_impacto_atingindo = 3
                    noticia_impacto = n
        except:
            continue

    # Aplicar penalidade do impacto
    if maior_impacto_atingindo > 0:
        score -= 1
        print(f"⚠ Notícia impacto {maior_impacto_atingindo} próxima: -1")
        print(f"📰 Impactando: {noticia_impacto['horario']} | {noticia_impacto['moeda']} | Impacto {noticia_impacto['impacto']} | {noticia_impacto['noticia']}")

    # Exibir notícias passada e futura
    if noticia_passada:
        print(f"🕒 Última notícia antes ou no sinal: {noticia_passada['horario']} | {noticia_passada['moeda']} | Impacto {noticia_passada['impacto']} | {noticia_passada['noticia']}")
    else:
        print("🕒 Nenhuma notícia antes ou no sinal.")

    if noticia_futura:
        print(f"🕒 Próxima notícia após o sinal: {noticia_futura['horario']} | {noticia_futura['moeda']} | Impacto {noticia_futura['impacto']} | {noticia_futura['noticia']}")
    else:
        print("🕒 Nenhuma notícia após o sinal.")

    print(f"🎯 Score final do sinal '{ativo}' às {horario_sinal.strftime('%H:%M:%S')}: {score}")
    return score


if __name__ == "__main__":
    dados = coletar_dados()
    score = analisar_sinal("EURUSD-OTC", "16:00:00", dados)

