from iqoptionapi.stable_api import IQ_Option
import time
from pprint import pprint

email = "diegodestroier@hotmail.com"
senha = "diego040324"

I_want_money = IQ_Option(email, senha)
I_want_money.connect()
time.sleep(5)

if not I_want_money.check_connect():
    print("❌ Falha na conexão")
    exit()

I_want_money.change_balance("PRACTICE")

abertos = I_want_money.get_all_open_time()
from pprint import pprint
pprint(abertos["binary"])  # Testa pares binários

