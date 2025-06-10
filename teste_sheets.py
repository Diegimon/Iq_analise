import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configurações
CREDENTIALS_FILE = 'uplifted-light-432518-k5-8d2823e4c54e.json'
SHEET_NAME = 'Trade'
ABA_DESTINO = 'Auto' 

# Autenticação
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
gc = gspread.authorize(credentials)

# Abrir aba específica
aba = gc.open(SHEET_NAME).worksheet(ABA_DESTINO)

# Escrever uma linha
aba.append_row(['Horário', 'Ativo', 'Direção', 'Resultado', 'Gale'])
