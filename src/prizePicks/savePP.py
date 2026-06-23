from datetime import datetime
import json
import sys
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

from .pp import prizepicks_cookie
from ..dashboard import export as dashboard_export

def prizepicks_entries_headers():
    """Headers for authenticated JSON API (e.g. v1/entries)."""
    return {
        'accept': 'application/json',
        'accept-language': 'en-US,en;q=0.8',
        'content-type': 'application/json',
        'cookie': prizepicks_cookie(),
        'origin': 'https://app.prizepicks.com',
        'priority': 'u=1, i',
        'referer': 'https://app.prizepicks.com/',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Brave";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'sec-gpc': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        'x-device-id': '279f02e9-94c7-4f29-8b5d-728de497ac1e',
        'x-device-info': 'name=,os=windows,osVersion=Windows NT 10.0; Win64; x64,isSimulator=false,platform=web,appVersion=web',
    }


def main():
    startDate = datetime.today()
    if len(sys.argv) < 2:
        startDate = datetime.strptime(input("Enter the first date to start recording: "), "%m/%d/%y")
    else:
        startDate = datetime.strptime(sys.argv[1], "%m/%d/%y")

    # Set up the Google Sheets API authorization
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", 'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(f'{os.path.dirname(os.path.abspath(__file__))}/../../googlesheets-credentials.json', scope)
    gc = gspread.authorize(credentials)

    sheet = gc.open('Prize Picks')
    worksheet = sheet.worksheet('Performance Data')

    # Find the bottom of the list of entries to start tracking
    row = len(worksheet.col_values(2)) + 2

    # Find column for non strategy P/L
    miscCol = 0
    miscRow = 0
    try:
        miscCol = worksheet.find('Random').col
        miscRow = len(worksheet.col_values(miscCol)) + 1
    except Exception:
        print('failed to find random')
        exit()

    url = 'https://api.prizepicks.com/v1/entries?filter=settled'
    resp = requests.Session().get(url, headers=prizepicks_entries_headers())
    if resp.status_code != 200:
        print(f'Error fetching entries: {resp.status_code}')
        print(resp.text)
        exit()
    
    dataFull = json.loads(resp.content)
    data = [entry for entry in dataFull['data'] if datetime.fromisoformat(entry['attributes']['created_at']).replace(tzinfo=None) >= startDate]
    data = sorted(data, key=lambda x: x['attributes']['created_at'])

    included = dataFull['included']

    predictions = {entry['id']: entry for entry in included if entry['type'] == 'prediction'}
    projections = {entry['id']: entry for entry in included if entry['type'] == 'projection'}
    promotions = {entry['id']: entry for entry in included if entry['type'] == 'promotion'}
    scores = {entry['id']: entry for entry in included if entry['type'] == 'score'}
    players = {entry['id']: entry for entry in included if entry['type'] == 'new_player'}
    projection_types = {entry['id']: entry for entry in included if entry['type'] == 'projection_type'}
    stat_types = {entry['id']: entry for entry in included if entry['type'] == 'stat_type'}

    for entry in data:
        attributes = entry['attributes']
        entryPredictions = entry['relationships']['predictions']['data']
        promo = entry['relationships']['promotion']['data']
        date = datetime.fromisoformat(attributes['created_at']).date().strftime('%m/%d/%y')
        wager = attributes['amount_bet_cents']/100.0
        profit = (attributes['amount_won_cents'] - attributes['amount_bet_cents'])/100.0
        if promo != None:
            type = promotions[promo['id']]['attributes']['type']
            if type.startswith('FreeEntry'):
                profit = attributes['amount_won_cents']/100.0
            elif type.startswith('ProtectedPlay'):
                profit = max(attributes['amount_won_cents'] - attributes['amount_bet_cents'], 0)/100.0

        fullEntry = []
        for p in entryPredictions:
            pred = predictions[p['id']]
            score = scores[pred['relationships']['score']['data']['id']]['attributes']
            ou = 'U' if pred['attributes']['wager_type'] == 'under' else 'O'
            if pred['attributes']['is_promo'] or not score['is_final'] or score['details'] == None or (score['unders_win_dnp'] and ou == 'O'):
                continue
            line = pred['attributes']['line_score']
            projection = projections[pred['relationships']['projection']['data']['id']]
            stat = getStatName(projection['attributes']['stat_display_name'])
            player = players[pred['relationships']['new_player']['data']['id']]['attributes']

            fullEntry.append({'name': player['name'], 'league': player['league'], 'stat': stat, 'ou': ou, 'result': checkResult(ou, line, score)})

        if not fullEntry:
            continue

        print(f'Date: {date}, Wager: {wager}, Profit: {profit}, Promo:{None if promo == None else type}')
        for e in fullEntry:
            print(e)
        if recordEntry():
            for i, e in enumerate(fullEntry):
                is_last = i == len(fullEntry) - 1
                row_values = formatSheetRow(date, e, profit if is_last else None, wager if is_last else None)
                end_col = 'J' if is_last else 'H'
                worksheet.update([row_values], f'B{row}:{end_col}{row}', raw=False)
                row += 1
            row += 1
        elif recordMisc():
            worksheet.update_cell(miscRow, miscCol, date)
            worksheet.update_cell(miscRow, miscCol+1, profit)
            miscRow += 1

    dashboard_export.export_all()
    exit()


def formatSheetRow(date, leg, profit=None, wager=None):
    """Build one worksheet row (columns B onward) for a leg.

    Profit and wager are entry-level fields written only on the final leg row
    (columns I and J); intermediate legs leave those columns blank.
    """
    row = [date, leg['name'], leg['league'], leg['stat'], '', leg['ou'], leg['result']]
    if profit is not None:
        row.append(profit)
    if wager is not None:
        row.append(wager)
    return row


def getStatName(name):
    match name:
        case 'Pts+Asts':
            return 'PA'
        case 'Pts+Rebs':
            return 'PR'
        case 'Pts+Rebs+Asts':
            return 'PRA'
        case 'Receiving Yards':
            return 'Rec Yards'

    return name
        
def checkResult(ou, line, score):
    if line == score['score']:
        return 'P'
    if ou == 'U':
        return 'H' if (score['score'] < line or score['unders_win_dnp']) else 'M'
    if ou == 'O':
        return 'H' if score['score'] > line else 'M'
    
def recordEntry():
    while True:
        yn = input('Record this entry? y/n: ').strip().lower()
        if yn == 'y':
            return True
        elif yn == 'n':
            return False
    
def recordMisc():
    while True:
        yn = input('Record this as a misc entry? y/n: ').strip().lower()
        if yn == 'y':
            return True
        elif yn == 'n':
            return False

if __name__ == '__main__':
    main()