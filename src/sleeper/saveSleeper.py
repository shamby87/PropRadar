from datetime import datetime, timezone
import json
import sys
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import pytz
from . import sleepUtils
from .. import utils
from ..dashboard import export as dashboard_export

def main():
    tz = pytz.timezone('US/Central')
    startDate = datetime.today()
    if len(sys.argv) < 2:
        startDate = datetime.strptime(input("Enter the first date to start recording: "), "%m/%d/%y").astimezone(tz)
    else:
        startDate = datetime.strptime(sys.argv[1], "%m/%d/%y").astimezone(tz)

    # # Set up the Google Sheets API authorization
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets", 'https://www.googleapis.com/auth/drive']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(f'{os.path.dirname(os.path.abspath(__file__))}/../../googlesheets-credentials.json', scope)
    gc = gspread.authorize(credentials)

    sheet = gc.open('Prize Picks')
    worksheet = sheet.worksheet('Sleeper Performance')

    # Find the bottom of the list of entries to start tracking
    row = len(worksheet.col_values(2)) + 2

    # Find column for non strategy P/L
    miscCol = 0
    miscRow = 0
    try:
        miscCol = worksheet.find('Random').col
        miscRow = len(worksheet.col_values(miscCol)) + 1
    except Exception:
        utils.logMsg('saveSleeper: could not find Random column; aborting', debug=True)
        return

    '''
    List available promos (POST)

    https://api.sleeper.app/graphql
    {
        "operationName": "list_eligible_promos",
        "query": "#graphql\n        query list_eligible_promos($user_id: Snowflake!, $location: Location) {\n          list_eligible_promos(user_id: $user_id, location: $location) {\n            amount\n            available_at\n            created\n            expires_at\n            metadata\n            promo_id\n            type\n            user_id\n          }\n        }",
        "variables": {
            "user_id": "970139967005552640",
            "location": {
            "country": "US",
            "region": "MN"
            }
        }
    }

    Completed parlays (POST)
    (Change status_filter: ["pending"] for open parlays)
    {
        "operationName": "my_parlays",
        "query": "#graphql\n        query my_parlays($limit: Int, $offset: Int, $status_filter: [String], $include_pick_counts: Boolean) {\n          my_parlays(limit: $limit, offset: $offset, status_filter: $status_filter, include_pick_counts: $include_pick_counts) {\n            created\n            currency_amount\n            currency_type\n            league_id\n            legs {\n              line {\n                closed\n                created\n                game_id\n                line_id\n                metadata\n                outcome\n                outcome_type\n                outcome_value\n                payout_multiplier\n                season\n                season_type\n                score {\n                  date\n                  game_id\n                  metadata\n                  season\n                  season_type\n                  sport\n                  start_time\n                  status\n                  week\n                  total_views\n                }\n                sport\n                status\n                subject\n                subject_id\n                subject_type\n                valid_close_duration_seconds\n                wager_type\n                line_type\n                pick_count\n              }\n              line_id\n              parlay_leg_id\n              status\n              graded_at\n            }\n            multiplier\n            parlay_id\n            status\n            user_id\n            display_data\n            graded_payout\n            graded_multiplier\n            graded_payout_boost\n            graded_at\n            max_payout\n            max_multiplier\n            max_payout_boost\n            possible_multipliers {\n              lost0\n              lost1\n              lost2\n            }\n          }\n        }",
        "variables": {
            "limit": 150,
            "offset": null,
            "status_filter": null,
            "include_pick_counts": true
        }
    }
    '''

    try:
        data = sleepUtils.getParlays(pending=False)
    except sleepUtils.SleeperApiError as e:
        utils.logMsg(f'saveSleeper: failed to fetch parlays ({e})')
        return
    data = sorted(data, key=lambda x: x['created'])

    for entry in data:
        epoch = entry['created']/1000
        date = datetime.fromtimestamp(epoch, timezone.utc).astimezone(tz)
        if date < startDate:
            continue
        date = date.date().strftime('%m/%d/%y')

        wager = float(entry['currency_amount'])
        profit = (float(entry['graded_payout']) - entry['currency_amount'])
        promo = entry['display_data'].get('promo_type', '')
        if promo == 'protected_pick':
            profit = max(profit, 0)

        fullEntry = buildLegRows(entry)

        utils.logMsg(f'Date: {date}, Profit: {profit}, Promo: {promo}')
        for e in fullEntry:
            utils.logMsg(e)
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

def formatSheetRow(date, leg, profit=None, wager=None):
    """Build one worksheet row (columns B onward) for a leg.

    Profit and wager are parlay-level fields written only on the final leg row
    (columns I and J); intermediate legs leave those columns blank.
    """
    row = [date, leg['name'], leg['league'], leg['stat'], leg['payout'], leg['ou'], leg['result']]
    if profit is not None:
        row.append(profit)
    if wager is not None:
        row.append(wager)
    return row


def buildLegRows(entry):
    """Build the sheet rows (one dict per leg) for a single parlay ``entry``.

    Canceled legs are skipped. Promo legs (Sleeper-provided discount/boost) are
    kept but written with a marker league (see :func:`getPromoLeague`) so the
    dashboard excludes them from PropRadar's own sport/stat/hit-rate analytics
    while still recording the leg's stat/payout/O-U/result.
    """
    parlayPromo = entry.get('display_data', {}).get('promo_type', '')
    fullEntry = []
    for p in entry['legs']:
        winLoss = p['status']
        line = p['line']
        if winLoss == 'canceled':
            continue
        ou = 'O' if line['outcome'] == 'over' else 'U'
        payout = line['payout_multiplier']
        name = f"{line['subject']['first_name']} {line['subject']['last_name']}"
        stat = getStatName(line['wager_type'])
        result = 'H' if winLoss == 'won' else ('M' if winLoss == 'lost' else 'P')

        if line['metadata'].get('promotion', '') == 'true':
            promoType = line['metadata'].get('promotion_type') or parlayPromo
            league = getPromoLeague(promoType)
        else:
            league = line['sport'].upper()

        fullEntry.append({'name': name, 'league': league, 'stat': stat, 'payout': payout, 'ou': ou, 'result': result})
    return fullEntry

def getPromoLeague(promoType):
    """Map a Sleeper promo type to the marker written in the League column.

    The dashboard treats these markers as promo (non-PropRadar) legs. Values
    mirror the ``promotion_type`` / ``display_data.promo_type`` strings returned
    by the ``my_parlays`` API.
    """
    match (promoType or '').lower():
        case 'over_boost':
            return 'Over Boost'
        case 'line_discount':
            return 'Line Discount'
    return 'Promo'

def getStatName(name):
    match name:
        case 'points':
            return 'Pts'
        case 'rebounds':
            return 'Reb'
        case 'assists':
            return 'Ast'
        case 'points_and_assists':
            return 'PA'
        case 'points_and_rebounds':
            return 'PR'
        case 'rebounds_and_assists':
            return 'RA'
        case 'pts_reb_ast':
            return 'PRA'
        case 'pass_completions':
            return 'Comp'
        case 'receiving_yards':
            return 'Rec Yards'
        case 'rushing_yards':
            return 'Rush Yards'
        case 'receptions':
            return 'Rec'

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