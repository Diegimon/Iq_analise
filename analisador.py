import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import pytz

# === Configuração do Google Sheets ===
CREDENTIALS_FILE = 'uplifted-light-432518-k5-8d2823e4c54e.json'
SHEET_NAME = 'Trade'
TIMEZONE = pytz.timezone('America/Sao_Paulo')

# === Pesos de cada critério ===
pesos = {
    "ativo_bom": 1,
    "ativo_ruim": -1,
    "horario_ruim": -1,
    "noticia_proxima": -1,
    "media_wins_ok": 1
}

print("=== INICIANDO ANÁLISE DE SINAIS ===")
print(f"Pesos configurados: {pesos}")
print()

# === Abertura da planilha ===
print("🔗 Conectando com Google Sheets...")
scope = ['https://www.googleapis.com/auth/spreadsheets',
         'https://www.googleapis.com/auth/drive.readonly']
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
gc = gspread.authorize(creds)
sheet = gc.open(SHEET_NAME)

aba_analise = sheet.worksheet("ANALISES")
aba_noticias = sheet.worksheet("NOTICIAS")
print("✅ Conexão estabelecida com sucesso!")
print()

def parse_horario(hora_str):
    return datetime.strptime(hora_str.strip(), "%H:%M").time()

def parse_percentual(valor):
    try:
        return float(valor.replace("%", "").replace(",", ".")) / 100
    except:
        return None

def obter_proximas_noticias(horario, limite=2):
    print(f"📰 Buscando notícias próximas ao horário {horario}...")
    noticias = aba_noticias.get_all_values()[1:]
    print(f"   Total de notícias encontradas: {len(noticias)}")
    
    hora_base = parse_horario(horario)
    proximas = []

    for i, linha in enumerate(noticias):
        try:
            hora_noticia = parse_horario(linha[0])
            impacto = int(linha[2]) if linha[2].isdigit() else 0
            delta = abs(datetime.combine(datetime.today(), hora_base) -
                        datetime.combine(datetime.today(), hora_noticia))
            proximas.append((delta.total_seconds(), linha[0], linha[1], impacto))
            print(f"   Notícia {i+1}: {linha[0]} - {linha[1]} (impacto {impacto}) - {int(delta.total_seconds()//60)}min de distância")
        except Exception as e:
            print(f"   ⚠️ Erro ao processar notícia {i+1}: {e}")
            continue

    proximas.sort()
    print(f"   Selecionando as {limite} notícias mais próximas...")
    return proximas[:limite]

def avaliar_sinal(ativo, horario):
    print(f"🔍 AVALIANDO SINAL: {ativo} às {horario}")
    print("=" * 50)
    
    score = 0
    criterios_aplicados = []
    linhas = aba_analise.get_all_values()
    print(f"   Dados carregados da planilha: {len(linhas)} linhas")

    ativo_normalizado = ativo.strip().upper()
    print(f"   Ativo normalizado: '{ativo_normalizado}'")
    print()

    # === Melhores Ativos de J20:L23 ===
    print("📊 CRITÉRIO 1: ANÁLISE DO ATIVO")
    print("   Carregando melhores ativos (J20:L23)...")
    melhores_raw = aba_analise.get("J20:L23")
    melhores_ativos = set()
    
    for i, linha in enumerate(melhores_raw):
        if len(linha) >= 3:
            nome = linha[0].strip().upper()
            winrate = parse_percentual(linha[2])
            if nome and winrate is not None:
                melhores_ativos.add(nome)
                print(f"   Melhor ativo {i+1}: {nome} (winrate: {winrate:.1%})")

    print(f"   Total de melhores ativos: {len(melhores_ativos)}")
    print(f"   Lista: {list(melhores_ativos)}")

    # === Piores Ativos de O20:Q23 ===
    print("   Carregando piores ativos (O20:Q23)...")
    piores_raw = aba_analise.get("O20:Q23")
    piores_ativos = set()
    
    for i, linha in enumerate(piores_raw):
        if len(linha) >= 3:
            nome = linha[0].strip().upper()
            winrate = parse_percentual(linha[2])
            if nome and winrate is not None:
                piores_ativos.add(nome)
                print(f"   Pior ativo {i+1}: {nome} (winrate: {winrate:.1%})")

    print(f"   Total de piores ativos: {len(piores_ativos)}")
    print(f"   Lista: {list(piores_ativos)}")

    # Avaliação do ativo
    if ativo_normalizado in melhores_ativos:
        score += pesos["ativo_bom"]
        criterios_aplicados.append("ativo: bom")
        print(f"   ✅ ATIVO CLASSIFICADO COMO BOM! Score += {pesos['ativo_bom']} (Total: {score})")
    elif ativo_normalizado in piores_ativos:
        score += pesos["ativo_ruim"]
        criterios_aplicados.append("ativo: ruim")
        print(f"   ❌ ATIVO CLASSIFICADO COMO RUIM! Score += {pesos['ativo_ruim']} (Total: {score})")
    else:
        criterios_aplicados.append("ativo: neutro")
        print(f"   ⚪ ATIVO NEUTRO (não está nas listas). Score inalterado (Total: {score})")
    print()

    # === Horários Ruins ===
    print("⏰ CRITÉRIO 2: ANÁLISE DO HORÁRIO")
    horarios_ruins = []
    print("   Carregando horários ruins (winrate < 80%)...")
    
    for i, l in enumerate(linhas[2:15]):  # linhas 3-16 da planilha
        if len(l) > 1 and l[0] and l[1]:
            winrate_hora = parse_percentual(l[1])
            if winrate_hora is not None:
                print(f"   Horário {l[0].strip()}: winrate {winrate_hora:.1%}", end="")
                if winrate_hora < 0.81:
                    horarios_ruins.append(l[0].strip())
                    print(" ❌ (RUIM)")
                else:
                    print(" ✅ (BOM)")

    print(f"   Total de horários ruins: {len(horarios_ruins)}")
    print(f"   Lista de horários ruins: {horarios_ruins}")

    if horario.strip() in horarios_ruins:
        score += pesos["horario_ruim"]
        criterios_aplicados.append("horário: ruim")
        print(f"   ❌ HORÁRIO CLASSIFICADO COMO RUIM! Score += {pesos['horario_ruim']} (Total: {score})")
    else:
        criterios_aplicados.append("horário: bom")
        print(f"   ✅ HORÁRIO CLASSIFICADO COMO BOM! Score inalterado (Total: {score})")
    print()

    # === Notícia próxima com impacto dinâmico ===
    print("📢 CRITÉRIO 3: ANÁLISE DE NOTÍCIAS PRÓXIMAS")
    noticias = aba_noticias.get_all_values()[1:]
    hora_base = parse_horario(horario)
    print(f"   Horário base: {hora_base}")
    print("   Verificando notícias com impacto 3 nos próximos 15 minutos...")
    
    noticia_encontrada = False
    for i, linha in enumerate(noticias):
        try:
            hora_noticia = parse_horario(linha[0])
            impacto = int(linha[2]) if linha[2].isdigit() else 0
            delta = abs(datetime.combine(datetime.today(), hora_base) -
                        datetime.combine(datetime.today(), hora_noticia))
            
            print(f"   Notícia {i+1}: {linha[0]} - {linha[1]} (impacto {impacto}) - {int(delta.total_seconds()//60)}min")
            
            if impacto >= 2:
                print(f"      → Impacto alto detectado! ({impacto})")
                if delta <= timedelta(minutes=15):
                    score += pesos["noticia_proxima"]
                    criterios_aplicados.append("notícia: muito ruim")
                    print(f"      ❌ NOTÍCIA MUITO PRÓXIMA E DE ALTO IMPACTO! Score += {pesos['noticia_proxima']} (Total: {score})")
                    noticia_encontrada = True
                    break
                else:
                    print(f"      → Mas está fora da janela de 15 minutos")

            else:
                print(f"      → Impacto baixo ({impacto}), ignorando")
                
        except Exception as e:
            print(f"   ⚠️ Erro ao processar notícia {i+1}: {e}")
            continue
    
    if not noticia_encontrada:
        criterios_aplicados.append("notícia: ok")
        print(f"   ✅ NENHUMA NOTÍCIA DE ALTO IMPACTO PRÓXIMA! Score inalterado (Total: {score})")

    if "horário: bom" in criterios_aplicados and "notícia: ok" in criterios_aplicados:
        score += 1
        criterios_aplicados.append("bônus: bom horário + notícia")
        print("Score +1 por bonus: bom horário + sem notícia✅")
    elif "ativo: bom" in criterios_aplicados and "horário: bom" in criterios_aplicados:
        score += 1
        criterios_aplicados.append("bônus: bom horário + ativo")
        print("Score +1 por bonus: bom horário + ativo✅")
    else:
        print("Nenhum bonus aplicado!❌")

    print()

    print("📋 RESUMO DA AVALIAÇÃO:")
    print(f"   Score final: {score}")
    print(f"   Critérios aplicados: {criterios_aplicados}")
    print()

    return score, criterios_aplicados

def recomendar(score):
    print("🎯 GERANDO RECOMENDAÇÃO:")
    if score >= 1:
        recomendacao = "✅ FORTE"
        print(f"   Score {score} → {recomendacao}")
    elif score == 0:
        recomendacao = "🟡 MODERADO" 
        print(f"   Score {score} → {recomendacao}")
    else:
        recomendacao = "⚠️ EVITE"
        print(f"   Score {score} → {recomendacao}")
    
    return recomendacao

def analisar_sinal(ativo, horario):
    print()
    print("🚀 INICIANDO ANÁLISE COMPLETA")
    print("=" * 60)
    
    score, criterios = avaliar_sinal(ativo, horario)
    recomendacao = recomendar(score)
    proximas_noticias = obter_proximas_noticias(horario)
    
    print()
    print("📊 RESULTADO FINAL:")
    print("=" * 30)
    print(f"Ativo: {ativo}")
    print(f"Horário: {horario}")
    print(f"Recomendação: {recomendacao}")
    print(f"Score: {score}")
    print()
    
    return recomendacao, score, criterios, proximas_noticias
