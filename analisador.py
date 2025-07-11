import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

CREDENTIALS_FILE = 'uplifted-light-432518-k5-8d2823e4c54e.json'
SHEET_NAME = 'Trade'

def coletar_dados():
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.readonly']
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
    gc = gspread.authorize(creds)

    sheet = gc.open(SHEET_NAME)
    aba_analise = sheet.worksheet("ANALISES")
    aba_noticias = sheet.worksheet("NOTICIAS")

    melhores = aba_analise.get("J20:J22")
    melhores_ativos = [linha[0].strip().upper() for linha in melhores if linha and linha[0]]

    piores = aba_analise.get("O20:O22")
    piores_ativos = [linha[0].strip().upper() for linha in piores if linha and linha[0]]

    linhas = aba_analise.get("A2:B26")
    horarios_info = []
    melhores_horarios = [h["horario"] for h in horarios_info if h["winrate"] >= 90.0]
    for linha in linhas:
        if len(linha) < 2:
            continue
        horario = linha[0].strip()
        winrate_raw = re.sub(r"[^\d,\.]", "", linha[1])  # remove tudo que não é número, vírgula ou ponto
        winrate_raw = winrate_raw.replace(",", ".")
        try:
            winrate = float(winrate_raw)
            print(f"Winrate importado {winrate_raw}")
            horarios_info.append({
                "horario": horario,
                "winrate": winrate                
            })
        
        except:
            print(f"[ANALISADOR] ❌ Ignorado horário '{horario}': winrate inválido '{linha[1]}'")
        
    # NOVO: Coletar ativos e winrate geral (J3:K16)
    ativos_winrate_geral = []
    ativos_winrate_linhas = aba_analise.get("J3:K16")
    for linha in ativos_winrate_linhas:
        if len(linha) < 2:
            continue
        nome = linha[0].strip().upper()
        winrate_raw = linha[1].replace("%", "").replace(",", ".").strip()
        try:
            winrate = float(winrate_raw)
            ativos_winrate_geral.append({
                "ativo": nome,
                "winrate": winrate
            })
        except:
            print(f"[ANALISADOR] ❌ Ignorado ativo '{nome}': winrate inválido '{linha[1]}'")

    noticias_lidas = []
    noticias = aba_noticias.get_all_values()[1:]
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

    return {
        "melhores_ativos": melhores_ativos,
        "piores_ativos": piores_ativos,
        "horarios_info": horarios_info,
        "melhores_horarios": melhores_horarios,  # novo
        "ativos_winrate_geral": ativos_winrate_geral,
        "noticias": noticias_lidas
    }


def analisar_sinal(ativo, horario_str, dados_coletados,direcao=None):
    score = 0
    ativo = ativo.strip().upper()
    criterios = []
    noticias_proximas = []
    winrate_horario = None

    winrate_ativo = None
    for item in dados_coletados["ativos_winrate_geral"]:
        if item["ativo"] == ativo.upper():
            winrate_ativo = item["winrate"]
            break

    try:
            horario_sinal = datetime.strptime(horario_str, "%H:%M:%S")
            hora_sinal = horario_sinal.strftime("%H:00")

    except:
        texto = f"[ANALISADOR] ❌ Erro: Horário do sinal inválido '{horario_str}'"
        print(texto)
        criterios.append(texto)
        return []

    melhores_ativos = dados_coletados["melhores_ativos"]
    piores_ativos = dados_coletados["piores_ativos"]
    horarios_info = dados_coletados["horarios_info"]
    noticias = dados_coletados["noticias"]

    
    for h in horarios_info:
        if h["horario"].strip() == hora_sinal:
            winrate_horario = h["winrate"]
            print(f"[ANALISADOR] ✅ Winrate do horário {hora_sinal} encontrado: {winrate_horario}")
            break
    else:
        print(f"[ANALISADOR] ⚠ Nenhum winrate encontrado para o horário {hora_sinal}")
    


    if ativo in piores_ativos:
        score -= 1
        texto = f"[ANALISADOR] ⚠ Ativo '{ativo}' está entre os piores"
        print(texto)
        criterios.append(texto)
    elif ativo in melhores_ativos:
        score += 1
        texto = f"[ANALISADOR] ✅ Ativo '{ativo}' está entre os melhores"
        print(texto)
        criterios.append(texto)

    piores_horarios = [h["horario"] for h in horarios_info if h["winrate"] < 80.0]

    if any(horario_sinal.strftime("%H:%M") == h for h in piores_horarios):
        score -= 1
        texto = f"[ANALISADOR] ⚠ Horário '{horario_sinal.strftime('%H:%M')}' está entre os piores"
        print(texto)
        criterios.append(texto)
    else:
        if ativo in melhores_ativos:
            score += 1
            texto = f"[ANALISADOR] ✅ Ativo bom e horário não ruim "
            print(texto)
            criterios.append(texto)

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

            if delta_min >= 0:
                if menor_delta_passado is None or delta_min < menor_delta_passado:
                    menor_delta_passado = delta_min
                    noticia_passada = n
            else:
                delta_min = abs(delta_min)
                if menor_delta_futuro is None or delta_min < menor_delta_futuro:
                    menor_delta_futuro = delta_min
                    noticia_futura = n

            delta = abs((horario_sinal - noticia_hora).total_seconds()) / 60

            if impacto == 1 and delta <= 10 and maior_impacto_atingindo < 1:
                maior_impacto_atingindo = 1
                noticia_impacto = n
            elif impacto == 2 and delta <= 30 and maior_impacto_atingindo < 2:
                maior_impacto_atingindo = 2
                noticia_impacto = n
            elif impacto == 3 and delta <= 60 and maior_impacto_atingindo < 3:
                maior_impacto_atingindo = 3
                noticia_impacto = n
        except:
            continue

    if maior_impacto_atingindo > 1:
        score -= 1
        texto = f"[ANALISADOR] ⚠ Notícia impacto {maior_impacto_atingindo} próxima"
        print(texto)
        criterios.append(texto)
        noticias_proximas.append(texto)

        texto = f"📰 Impactando:\n {noticia_impacto['horario']} | {noticia_impacto['moeda']} | Impacto {noticia_impacto['impacto']} |\n {noticia_impacto['noticia']}"
        print(texto)
        noticias_proximas.append(texto)

    if noticia_passada:
        texto = f"🕒 Última notícia antes ou no sinal:\n {noticia_passada['horario']} | {noticia_passada['moeda']} | Impacto {noticia_passada['impacto']} |\n {noticia_passada['noticia']}"
    else:
        texto = "🕒? Nenhuma notícia antes ou no sinal."
    print(texto)
    noticias_proximas.append(texto)

    if noticia_futura:
        texto = f"🕒 Próxima notícia após o sinal:\n {noticia_futura['horario']} | {noticia_futura['moeda']} | Impacto {noticia_futura['impacto']} |\n {noticia_futura['noticia']}"
    else:
        texto = "🕒? Nenhuma notícia após o sinal."
    print(texto)
    noticias_proximas.append(texto)

    print(f"[ANALISADOR] 🎯 Score final do sinal '{ativo}' às {horario_sinal.strftime('%H:%M:%S')}: {score}")

    print("\n[ANALISADOR] ✅ Critérios aplicados:")
    for c in criterios:
        print(f"- {c}")
    print("\n[ANALISADOR] 📰 Notícias próximas:")
    for n in noticias_proximas:
        print(f"{n}")

    if score == 1:
        recomendacao = "✅ RECOMENDADO"
    elif score > 1:
        recomendacao = "✅ FORTEMENTE RECOMENDADO"
    elif score == 0:
        recomendacao = "🟡 MODERADO"
    else:
        recomendacao = "⚠️ NÃO RECOMENDADO"

    return [{
        "ativo": ativo,
        "horario": horario_sinal.strftime('%H:%M:%S'),
        "winrate_horario": winrate_horario,  # novo campo
        "direcao": direcao,
        "winrate_ativo": winrate_ativo,
        "score": score,
        "recomendacao": recomendacao,
        "criterios": criterios,
        "noticias_proximas": noticias_proximas
    }]

