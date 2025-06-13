from iqoptionapi.stable_api import IQ_Option
import time
import traceback

# === LOGIN ===
email = "diegodestroier@hotmail.com"
senha = "diego040324"
par = "EURUSD"       # ativo
valor = 10            # valor da entrada
direcao = "call"      # ou "put"
tempo = 1             # em minutos

try:
    print("🔄 Conectando...")
    I_want_money = IQ_Option(email, senha)
    I_want_money.connect()
    time.sleep(5)

    if not I_want_money.check_connect():
        print("❌ ERRO: Falha na conexão - Verifique credenciais")
        exit()
    print("✅ Conectado à conta")

    # Troca para conta de treino
    try:
        I_want_money.change_balance("PRACTICE")
        print("✅ Conta alterada para PRACTICE")
    except Exception as e:
        print(f"❌ ERRO ao mudar conta: {e}")

    # === VERIFICA PAR ABERTO ===
    max_tentativas = 10
    for tentativa in range(max_tentativas):
        try:
            abertos = I_want_money.get_all_open_time()
            if abertos["digital"].get(par, {}).get("open", False):
                print(f"✅ Par {par} está aberto para entrada")
                break
            else:
                print(f"⏳ Aguardando abertura do par {par}...")
        except Exception as e:
            print("⚠️ IQ Option ainda não respondeu com os pares digitais.")
        time.sleep(1)
    else:
        print("❌ Timeout: par não ficou disponível a tempo.")
        exit()

    # === ENTRADA ===
    try:
        status, trade_id = I_want_money.buy(valor, par, direcao, tempo)
        if status:
            print(f"✅ Entrada executada com sucesso - ID: {trade_id}")
        else:
            print("❌ ERRO: Entrada falhou")
            print(f"Saldo atual: {I_want_money.get_balance()}")
    except Exception:
        print("❌ ERRO na execução:")
        traceback.print_exc()

except Exception as e:
    print(f"❌ ERRO GERAL: {e}")
    print("Verifique: 1) Internet 2) Credenciais 3) API atualizada")
