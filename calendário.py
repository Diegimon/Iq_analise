import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# Configuração da localização e timezone
TIMEZONE = pytz.timezone('UTC')
URL = "https://br.investing.com/economic-calendar/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

# Configuração do Google Sheets
CREDENTIALS_FILE = 'uplifted-light-432518-k5-8d2823e4c54e.json'
SHEET_NAME = 'Trade'
WORKSHEET_NAME = 'NOTICIAS'

# Lista para armazenar os eventos extraídos
def coletar_eventos():
    eventos = []
    response = requests.get(URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    tabela = soup.find("table", {"id": "economicCalendarData"})
    if not tabela:
        print("Tabela de eventos não encontrada.")
        return eventos

    linhas = tabela.find_all("tr", class_=lambda x: x != "thead")
    for linha in linhas:
        colunas = linha.find_all("td")
        if len(colunas) < 6:
            continue

        horario_raw = colunas[0].get_text(strip=True)
        moeda = colunas[1].get_text(strip=True)
        impacto_icons = colunas[2].find_all("i")
        impacto = sum(1 for icon in impacto_icons if 'grayFullBullishIcon' in icon.get("class", []))
        evento = colunas[3].get_text(strip=True)

        try:
            horario = datetime.strptime(horario_raw, "%H:%M")
            horario = TIMEZONE.localize(horario)
        except:
            continue

        eventos.append([
            horario.strftime("%H:%M"),
            moeda,
            impacto,
            evento
        ])

    return eventos

def salvar_no_google_sheets(eventos):
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.readonly'
    ]
    credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scope)
    gc = gspread.authorize(credentials)
    sheet = gc.open(SHEET_NAME)
    worksheet = sheet.worksheet(WORKSHEET_NAME)

    # Limpa apenas colunas A-D (1 a 4)
    cell_range = f"A1:D{worksheet.row_count}"
    empty_data = [["" for _ in range(4)] for _ in range(worksheet.row_count)]
    worksheet.update(cell_range, empty_data)

    # Adiciona cabeçalho e eventos
    worksheet.update("A1:D1", [['Horário', 'Moeda', 'Impacto', 'Evento']])
    if eventos:
        worksheet.update(f"A2:D{1 + len(eventos)}", eventos, value_input_option='RAW')

def main():
    eventos = coletar_eventos()
    if eventos:
        salvar_no_google_sheets(eventos)
        print(f"{len(eventos)} eventos salvos na planilha '{SHEET_NAME}' na aba '{WORKSHEET_NAME}'.")
    else:
        print("Nenhum evento encontrado.")

if __name__ == '__main__':
    main()
