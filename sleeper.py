import requests
import pandas as pd
import numpy as np
import time
import json
import sys
import statistics as stats
import os
from datetime import date, timedelta, datetime, timezone
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get('API_KEY')

# The-odds-api.com
REGIONS = 'us' # uk | us | eu | au. Multiple can be specified if comma delimited
MARKETS = 'h2h' # h2h | spreads | totals. Multiple can be specified if comma delimited
ODDS_FORMAT = 'decimal' # decimal | american
DATE_FORMAT = 'iso' # iso | unix

s = ""

if len(sys.argv) >= 2:
    s = sys.argv[1]
else:
    s = str(input("Which stat? strikeouts, pass yards, completions, rush yards, receptions, rec yards, SOG, NBA points: "))

match s:
    case "NFL":
        SPORT = 'americanfootball_nfl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_pass_yds', 'player_pass_completions', 'player_rush_yds', 'player_receptions', 'player_reception_yds'] #The-odds-api
        sleeper_stats = ['Pass Yards', 'Pass Completions', 'Rush Yards', 'Receptions', 'Receiving Yards'] # Sleeper
        league = "nfl"
    case "NBA":
        SPORT = 'basketball_nba' # use the sport_key from the /sports endpoint 
        api_stats = ['player_points', 'player_assists', 'player_rebounds', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists', 'player_rebounds_assists'] #The-odds-api
        sleeper_stats = ['points', 'assists', 'rebounds', 'pts_reb_ast', 'points_and_rebounds', 'points_and_assists', 'rebounds_and_assists'] # Sleeper
        league = "nba"
    case "CBB":
        SPORT = 'basketball_ncaab' # use the sport_key from the /sports endpoint 
        api_stats = ['player_points', 'player_assists', 'player_rebounds', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists'] #The-odds-api
        sleeper_stats = ['Points', 'Assists', 'Rebounds', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts'] # Sleeper
        league = "cbb"
    case "NHL":
        SPORT = 'icehockey_nhl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_shots_on_goal', 'player_points', 'player_total_saves'] #The-odds-api
        sleeper_stats = ['Shots on Goal', 'Points', 'Goalie Saves'] # Sleeper
        league = "nhl"
    case "MLB":
        SPORT = 'baseball_mlb' # use the sport_key from the /sports endpoint 
        api_stats = ['pitcher_strikeouts', 'pitcher_outs'] #The-odds-api
        sleeper_stats = ['Pitcher Strikeouts', 'Pitching Outs'] # Sleeper
        league = "mlb"
    case _:
        print(f'Unknown stat: {s}')
        exit()

start_d = 0
if len(sys.argv) >= 3:
    start_d = int(sys.argv[2])
else:
    start_d = int(input("Start day: Today + (days): "))

end_d = 0
if len(sys.argv) >= 4:
    end_d = int(sys.argv[3])
else:
    end_d = int(input("End day: Today + (days): "))

offset = 6 # CST
start_day = datetime.now(timezone(-timedelta(hours=offset))).date() + timedelta(days=start_d) # Needed to convert to CST
end_day = datetime.now(timezone(-timedelta(hours=offset))).date() + timedelta(days=end_d) 

lines_url = f"https://api.sleeper.app/lines/available?sports[]={league}&date_from={start_day.isoformat}&date_to={end_day.isoformat}&dynamic=true&eg=5.control"
playerIDs_url = f"https://api.sleeper.app/v1/players/{league}"

req = requests.get(lines_url)
data = req.content
if req.status_code != 200:
    print(f'Lines request failed w status {req.status_code}: {req.reason}')
    print(data)
    exit()
    
df = json.loads(data)
lines_data = pd.json_normalize(df, max_level=3)

req = requests.get(playerIDs_url)
data = req.content
if req.status_code != 200:
    print(f'Player IDs request failed w status {req.status_code}: {req.reason}')
    print(data)
    exit()
    
playerIDs = json.loads(data) # Dict where index is the player ID

filtered = lines_data.where((lines_data['wager_type'].isin(sleeper_stats)) & (lines_data['game_status']=="pre_game") & (lines_data['line_type']=="normal") & (lines_data['outcome_type']=="over_under"))
filtered = filtered[~filtered['subject_id'].isna()]

players = {stat: {} for stat in sleeper_stats}
for i in range(len(filtered)):
    player = filtered.iloc[i]
    id = player['subject_id']
    name = playerIDs[id]['full_name'].lower()
    stat = player['wager_type']
    players[stat][name] = {}
    for option in player['options']:
        players[stat][name][option['outcome']] = { # 'Outcome' is over or under
            'line': option['outcome_value'],
            'payout': float(option['payout_multiplier']),
            'otherBooks': [],
            'otherLines': [],
            'avgAdvantage': 0,
            'stdev': 0
        }

# print(json.dumps(players, indent=2))

odds_response = requests.get(
    f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds',
    params={
        'api_key': API_KEY,
        'regions': REGIONS,
        'markets': MARKETS,
        'oddsFormat': ODDS_FORMAT,
        'dateFormat': DATE_FORMAT,
    }
)

events = []

if odds_response.status_code != 200:
    print(f'Failed to get odds: status_code {odds_response.status_code}, response body {odds_response.text}')
    exit()
else:
    odds_json = odds_response.json()
    print('Number of events:', len(odds_json))
    # print(odds_json)

    for e in odds_json:
        event_date = datetime.fromisoformat(e['commence_time']) - timedelta(hours=offset)
        if event_date.date() >= start_day and event_date.date() <= end_day:
            events.append(e['id'])

    # Check the usage quota
    print('Remaining requests', odds_response.headers['x-requests-remaining'])
    print('Used requests', odds_response.headers['x-requests-used'])

for api_stat, sleeper_stat in zip(api_stats, sleeper_stats):
    for event in events:
        event_test = requests.get(
            f'https://api.the-odds-api.com/v4/sports/{SPORT}/events/{event}/odds',
            params={
                'api_key': API_KEY,
                'regions': REGIONS,
                'markets': api_stat,
                'oddsFormat': ODDS_FORMAT,
                'dateFormat': DATE_FORMAT,
            }
        )

        # NOTE: Price = the payout on a win, e.g 1.91x would be roughly -110 odds
        # EV: ((1/overPayout)*(line+0.5) + (1/underPayout)*(line-0.5)) / (1/overPayout + 1/underPayout)

        if event_test.status_code != 200:
            print(f'Failed to get odds: status_code {event_test.status_code}, response body {event_test.text}')

        else:
            odds_json = event_test.json()
            print('Number of events:', len(odds_json))
            # print(odds_json)

            # Check the usage quota
            print('Remaining requests', event_test.headers['x-requests-remaining'])
            print('Used requests', event_test.headers['x-requests-used'])

            for book in odds_json['bookmakers']:
                for outcome in book['markets'][0]['outcomes']:
                    name = outcome["description"].lower()
                    if not name in players[sleeper_stat]:
                        continue

                    # Add this book's price entry if it has the same line as sleeper
                    if outcome['point'] == players[sleeper_stat][name][outcome['name'].lower()]['line']:
                        players[sleeper_stat][name][outcome['name'].lower()]['otherBooks'].append(outcome['price'])
                    else:
                        # Otherwise, add this alt line to the list
                        players[sleeper_stat][name][outcome['name'].lower()]['otherLines'].append({'line': outcome['point'], 'payout': outcome['price']})

    # After we get all the values from the books, find the avg and compare to the line
    for player in players[sleeper_stat]:
        for outcome in ['over', 'under']:
            if len(players[sleeper_stat][player][outcome]['otherBooks']) > 1:
                # A ratio > 1 means this payout is 'avgAdvantage' times greater than average across other books
                players[sleeper_stat][player][outcome]['avgAdvantage'] = players[sleeper_stat][player][outcome]['payout'] / stats.fmean(players[sleeper_stat][player][outcome]['otherBooks'])
                # players[sleeper_stat][player][outcome]['stdev'] = stats.stdev(players[sleeper_stat][player][outcome]['otherBooks'])

top_plays = {}
# After all is done, print the top plays for each stat line
for sleeper_stat in sleeper_stats:
    # Sort by greatest avgAdvantage, only look at better of over/under for each player 
    print(f"{sleeper_stat}:")
    result = dict(sorted(players[sleeper_stat].items(), key=lambda item: max(item[1]['over']['avgAdvantage'], item[1]['under']['avgAdvantage']), reverse=True))

    num = min(6, len(result)) # Only print top 6 plays max
    for r in result.items():
        # if abs(r[1]['avgAdvantage']) < THRESHOLD: # Still want to show the first play no matter what, but once we hit shitty plays we should stop
        #     if num != min(6, len(result)):
        #         break
        if num > 0:
            info = r[1]['over'] if r[1]['over']['avgAdvantage'] >= r[1]['under']['avgAdvantage'] else r[1]['under']
            ou = "Over" if r[1]['over']['avgAdvantage'] >= r[1]['under']['avgAdvantage'] else "Under"
            print(f"\t{r[0]} - line: {ou} {info['line']}, Avg Advantage: {round(info['avgAdvantage'], 4)}, len: {len(info['otherBooks'])}")
            # Add this play to our potential best parlay
            if r[0] not in top_plays:
                top_plays[r[0]] = {'ou': ou, 'payout': info['payout'], 'line': info['line'], 'avgAdvantage': info['avgAdvantage'], 'len': len(info['otherBooks']), 'SleeperStat': sleeper_stat}
            elif top_plays[r[0]]['avgAdvantage'] < info['avgAdvantage']: # Replace if they have a better dif in a different line
                top_plays[r[0]] = {'ou': ou, 'payout': info['payout'], 'line': info['line'], 'avgAdvantage': info['avgAdvantage'], 'len': len(info['otherBooks']), 'SleeperStat': sleeper_stat}

        num -= 1

# Print out the full best play
result = dict(sorted(top_plays.items(), key=lambda item: abs(item[1]['avgAdvantage']), reverse=True))
num = min(6, len(result)) # Only print top 6 plays max
print("\nFull best play:")
for r in result.items():
    if num > 0:
        print(f"\t{r[0]} - line: {r[1]['ou']} {r[1]['line']} {r[1]['SleeperStat']}, payout: {r[1]['payout']}x, avg advantage: {round(r[1]['avgAdvantage'], 4)}, len: {r[1]['len']}")

    num -= 1