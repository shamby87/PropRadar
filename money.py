import math
import os
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import numpy as np
import time
import json
from datetime import date, timedelta, datetime, timezone
import statistics as stats
import requests
import sys
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get('API_KEY')

THRESHOLD = 0.65 # ignore plays that are lower than this

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
        pp_stats = ['Pass Yards', 'Pass Completions', 'Rush Yards', 'Receptions', 'Receiving Yards'] # Prizepicks
        league = "NFL"
    case "NBA":
        SPORT = 'basketball_nba' # use the sport_key from the /sports endpoint 
        api_stats = ['player_points', 'player_assists', 'player_rebounds', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists', 'player_rebounds_assists'] #The-odds-api
        pp_stats = ['Points', 'Assists', 'Rebounds', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts', 'Rebs+Asts'] # Prizepicks
        league = "NBA"
    case "CBB":
        SPORT = 'basketball_ncaab' # use the sport_key from the /sports endpoint 
        api_stats = ['player_points', 'player_assists', 'player_rebounds', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists'] #The-odds-api
        pp_stats = ['Points', 'Assists', 'Rebounds', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts'] # Prizepicks
        league = "CBB"
    case "NHL":
        SPORT = 'icehockey_nhl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_shots_on_goal', 'player_points', 'player_total_saves'] #The-odds-api
        pp_stats = ['Shots on Goal', 'Points', 'Goalie Saves'] # Prizepicks
        league = "NHL"
    case "MLB":
        SPORT = 'baseball_mlb' # use the sport_key from the /sports endpoint 
        api_stats = ['pitcher_strikeouts', 'pitcher_outs'] #The-odds-api
        pp_stats = ['Pitcher Strikeouts', 'Pitching Outs'] # Prizepicks
        league = "MLB"
    case "pass yards":
        SPORT = 'americanfootball_nfl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_pass_yds'] #The-odds-api
        pp_stats = ['Pass Yards'] # Prizepicks
        league = "NFL"
    case "completions":
        SPORT = 'americanfootball_nfl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_pass_completions'] #The-odds-api
        pp_stats = ['Pass Completions'] # Prizepicks
        league = "NFL"
    case "rush yards":
        SPORT = 'americanfootball_nfl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_rush_yds'] #The-odds-api
        pp_stats = ['Rush Yards'] # Prizepicks
        league = "NFL"
    case "receptions":
        SPORT = 'americanfootball_nfl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_receptions'] #The-odds-api
        pp_stats = ['Receptions'] # Prizepicks
        league = "NFL"
    case "rec yards":
        SPORT = 'americanfootball_nfl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_reception_yds'] #The-odds-api
        pp_stats = ['Receiving Yards'] # Prizepicks
        league = "NFL"
    case "NBA points":
        SPORT = 'basketball_nba' # use the sport_key from the /sports endpoint 
        api_stats = ['player_points'] #The-odds-api
        pp_stats = ['Points'] # Prizepicks
        league = "NBA"
    case "NBA assists":
        SPORT = 'basketball_nba' # use the sport_key from the /sports endpoint 
        api_stats = ['player_assists'] #The-odds-api
        pp_stats = ['Assists'] # Prizepicks
        league = "NBA"
    case "NBA rebounds":
        SPORT = 'basketball_nba' # use the sport_key from the /sports endpoint 
        api_stats = ['player_rebounds'] #The-odds-api
        pp_stats = ['Rebounds'] # Prizepicks
        league = "NBA"
    case "strikeouts":
        SPORT = 'baseball_mlb' # use the sport_key from the /sports endpoint 
        api_stats = ['pitcher_strikeouts'] #The-odds-api
        pp_stats = ['Pitcher Strikeouts'] # Prizepicks
        league = "MLB"
    case "SOG":
        SPORT = 'icehockey_nhl' # use the sport_key from the /sports endpoint 
        api_stats = ['player_shots_on_goal'] #The-odds-api
        pp_stats = ['Shots On Goal'] # Prizepicks
        league = "NHL"
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

graphical = True
if len(sys.argv) >= 5:
    graphical = False

url = "https://api.prizepicks.com/projections"

data = None
if graphical:
    driver = webdriver.Firefox()
    ############## PRIZEPICKS ################################################

    driver.get(url)

    time.sleep(2)

    driver.find_element(By.ID, "rawdata-tab").click()

    time.sleep(2)

    data = driver.find_element(By.CLASS_NAME, "data").text
    
    driver.quit()
else:
    header = {
        "Host": "api.prizepicks.com",
        "User-Agent": "Mozilla/5.0 (X11; Linux aarch64; rv:102.0) Gecko/20100101 Firefox/102.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Alt-Used": "api.prizepicks.com",
        "Cookie": "_ga_7D11YVFKG7=GS1.1.1703792369.1.1.1703792388.0.0.0; _ga=GA1.1.1935787825.1703792370; _gcl_au=1.1.1966627405.1703792370; __podscribe_prizepicks_referrer=_; __podscribe_prizepicks_landing_url=https://www.prizepicks.com/api/projections; __podscribe_did=d1b96d42-483b-4a2e-d463-2aae0d6c0115; _sp_id.9177=b6c5e7a4-94b3-4e5c-9e83-645101a06ce1.1703792371.1.1703792371.1703792371.f933723f-5680-43fc-9ba0-f96350e87379; _rdt_uuid=1703792370847.9dfda275-fafd-4aa5-aa6d-c581eb28517b; _scid=09a375bd-622e-4ddc-a8a4-0fd936ba93d5; _scid_r=09a375bd-622e-4ddc-a8a4-0fd936ba93d5; ajs_anonymous_id=b7795cc5-3bde-412b-86f0-169f7eab0843; _lab=3377700667481019; _sctr=1%7C1703721600000; _fbp=fb.1.1703792373009.143617702; intercom-id-qmdeaj0t=5b644d51-da13-406b-835c-cac2d17dcc56; intercom-session-qmdeaj0t=; intercom-device-id-qmdeaj0t=0311a048-ce76-4331-908e-46f6abda9bd3; _cfuvid=bcUGXuqkvyuaoB81pj1WaP9QUpusXBQapEDmm2SdipA-1703792401148-0-604800000",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "TE": "trailers",
    }

    req = requests.get(url, headers=header)
    data = req.content
    if req.status_code != 200:
        print(f'Request failed w status {req.status_code}: {req.reason}')
        print(data)
        exit()

# print(data)
df = json.loads(data)
data = pd.json_normalize(df['data'], max_level=3)
included = pd.json_normalize(df['included'], max_level=3)
inc_cop = included[included['type'] == 'new_player'].copy().dropna(axis=1)
data = pd.merge(data
                , inc_cop
                , how='left'
                , left_on=['relationships.new_player.data.id'
                            ,'relationships.new_player.data.type']
                , right_on=['id', 'type']
                , suffixes=('', '_new_player'))
print(data.head(3))
# exit()
filtered = data.where((data['attributes.stat_type'].isin(pp_stats)) & (data['attributes.status']=="pre_game"))
filtered = filtered[~filtered['attributes.stat_type'].isna()]

players = {stat: {} for stat in pp_stats} # Organize the players by stats, then by name
for i in range(0, len(filtered)):
    player = filtered.iloc[i]
    desc = player['attributes.description']
    l = player['attributes.league']
    stat_type = player['attributes.odds_type']
    t = date.fromisoformat(player['attributes.start_time'].split("T")[0])
    if t < start_day or t > end_day:
        continue
    if l == league and "inning" not in desc.lower() and "SZN" not in l and "1H" not in l and "half" not in desc.lower() and "combo" not in desc.lower() and "first" not in desc.lower() and stat_type == "standard" and "1Q" not in desc and "4Q" not in desc and "4Q" not in l:
        name = player['attributes.name'].lower()
        stat = player['attributes.stat_type']
        line = player['attributes.line_score']
        # print(f"{name}, {stat}, {line}, {t}")

        players[stat][name] = {
            'PPLine': line,
            'otherBooks': [],
            'avgDif': 0
        }

# print(players)
# quit()
# players = {'Points': {'caleb love': {'PPLine': 21.5, 'otherBooks': [], 'avgDif': 0}, 'keshad johnson': {'PPLine': 12.5, 'otherBooks': [], 'avgDif': 0}, 'kylan boswell': {'PPLine': 9.0, 'otherBooks': [], 'avgDif': 0}, 'oumar ballo': {'PPLine': 13.5, 'otherBooks': [], 'avgDif': 0}, 'pelle larsson': {'PPLine': 12.5, 'otherBooks': [], 'avgDif': 0}, 'kawhi leonard': {'PPLine': 5.5, 'otherBooks': [], 'avgDif': 0}, 'jimmy butler': {'PPLine': 5.5, 'otherBooks': [], 'avgDif': 0}, 'paul george': {'PPLine': 5.0, 'otherBooks': [], 'avgDif': 0}, 'bam adebayo': {'PPLine': 5.0, 'otherBooks': [], 'avgDif': 0}, 'james harden': {'PPLine': 3.5, 'otherBooks': [], 'avgDif': 0}, 'terry rozier': {'PPLine': 3.5, 'otherBooks': [], 'avgDif': 0}, 'norman powell': {'PPLine': 3.5, 'otherBooks': [], 'avgDif': 0}, 'russell westbrook': {'PPLine': 2.5, 'otherBooks': [], 'avgDif': 0}, 'damian lillard': {'PPLine': 27.5, 'otherBooks': [], 'avgDif': 0}, 'lauri markkanen': {'PPLine': 23.5, 'otherBooks': [], 'avgDif': 0}, 'collin sexton': {'PPLine': 21.0, 'otherBooks': [], 'avgDif': 0}, 'malik beasley': {'PPLine': 13.5, 'otherBooks': [], 'avgDif': 0}, 'john collins': {'PPLine': 13.5, 'otherBooks': [], 'avgDif': 0}, 'simone fontecchio': {'PPLine': 8.5, 'otherBooks': [], 'avgDif': 0}, 'giannis antetokounmpo': {'PPLine': 35.5, 'otherBooks': [], 'avgDif': 0}, 'jordan clarkson': {'PPLine': 19.5, 'otherBooks': [], 'avgDif': 0}, 'kelly olynyk': {'PPLine': 6.5, 'otherBooks': [], 'avgDif': 0}, 'keyonte george': {'PPLine': 10.5, 'otherBooks': [], 'avgDif': 0}, 'walker kessler': {'PPLine': 6.5, 'otherBooks': [], 'avgDif': 0}, 'aaron gordon': {'PPLine': 14.0, 'otherBooks': [], 'avgDif': 0}, 'anfernee simons': {'PPLine': 26.5, 'otherBooks': [], 'avgDif': 0}, 'jamal murray': {'PPLine': 22.5, 'otherBooks': [], 'avgDif': 0}, 'kentavious caldwell-pope': {'PPLine': 10.5, 'otherBooks': [], 'avgDif': 0}, 'michael porter jr.': {'PPLine': 14.5, 'otherBooks': [], 'avgDif': 0}, 'nikola jokic': {'PPLine': 26.0, 'otherBooks': [], 'avgDif': 0}, 'reggie jackson': {'PPLine': 9.5, 'otherBooks': [], 'avgDif': 0}, 'matisse thybulle': {'PPLine': 6.5, 'otherBooks': [], 'avgDif': 0}, 'peyton watson': {'PPLine': 7.5, 'otherBooks': [], 'avgDif': 0}, 'kris murray': {'PPLine': 7.5, 'otherBooks': [], 'avgDif': 0}}}


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

for api_stat, pp_stat in zip(api_stats, pp_stats):
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
                unders = 0
                overs = 0
                names = []
                for i in book['markets'][0]['outcomes']:
                    if i['name'] == 'Under':
                        unders += 1
                    else:
                        overs += 1
                    if i['description'] not in names:
                        names.append(i['description'])
                if (unders != overs) or (unders != len(names)):
                    continue
                for i in range(0, len(book['markets'][0]['outcomes']), 2):
                    outcome = book['markets'][0]['outcomes'][i]
                    otherOutcome = book['markets'][0]['outcomes'][i + 1]

                    if outcome['name'] == otherOutcome['name']:
                        # We want to skip this wack ass book
                        break
                    name = outcome["description"].lower()
                    if not name in players[pp_stat]:
                        continue

                    overLine = 0
                    overPayout = 0
                    underLine = 0
                    underPayout = 0

                    if outcome['name'] == 'Over':
                        overLine = outcome["point"]+0.5
                        overPayout = 1/outcome["price"]
                        underLine = otherOutcome["point"]-0.5
                        underPayout = 1/otherOutcome["price"]
                    else:
                        underLine = outcome["point"]-0.5
                        underPayout = 1/outcome["price"]
                        overLine = otherOutcome["point"]+0.5
                        overPayout = 1/otherOutcome["price"]
                    
                    players[pp_stat][name]['otherBooks'].append(((overPayout*overLine) + (underPayout*underLine)) / (overPayout + underPayout))
        # exit()

    # After we get all the values from the books, find the avg and compare to the PPLine
    for player in players[pp_stat]:
        if len(players[pp_stat][player]['otherBooks']) > 3:
            players[pp_stat][player]['avgDif'] = players[pp_stat][player]['PPLine'] - stats.fmean(players[pp_stat][player]['otherBooks'])

top_plays = {}
# After all is done, print the top plays for each stat line
for pp_stat in pp_stats:
    # Sort by greatest abs value
    print(f"{pp_stat}:")
    result = dict(sorted(players[pp_stat].items(), key=lambda item: abs(item[1]['avgDif']), reverse=True))

    num = min(6, len(result)) # Only print top 6 plays max
    for r in result.items():
        if abs(r[1]['avgDif']) < THRESHOLD: # Still want to show the first play no matter what, but once we hit shitty plays we should stop
            if num != min(6, len(result)):
                break
        if num > 0:
            print(f"\t{r[0]} - PPLine: {'Over' if r[1]['avgDif'] < 0 else 'Under'} {r[1]['PPLine']}, Avg Diff: {round(r[1]['avgDif'], 4)}, len: {len(r[1]['otherBooks'])}")
            # Add this play to our potential best parlay
            if r[0] not in top_plays:
                top_plays[r[0]] = {'PPLine': r[1]['PPLine'], 'avgDif': r[1]['avgDif'], 'len': len(r[1]['otherBooks']), 'PPStat': pp_stat}
            elif top_plays[r[0]]['PPLine'] < r[1]['PPLine']: # Replace if they have a better dif in a different line
                top_plays[r[0]] = {'PPLine': r[1]['PPLine'], 'avgDif': r[1]['avgDif'], 'len': len(r[1]['otherBooks']), 'PPStat': pp_stat}

        num -= 1

# Print out the full best play
result = dict(sorted(top_plays.items(), key=lambda item: abs(item[1]['avgDif']), reverse=True))
num = min(6, len(result)) # Only print top 6 plays max
print("\nFull best play:")
for r in result.items():
    if num > 0:
        print(f"\t{r[0]} - PPLine: {'Over' if r[1]['avgDif'] < 0 else 'Under'} {r[1]['PPLine']} {r[1]['PPStat']}, Avg Diff: {round(r[1]['avgDif'], 4)}, len: {r[1]['len']}")

    num -= 1