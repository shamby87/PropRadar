from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
import numpy as np
import time
import json
from datetime import date, timedelta, datetime, timezone
import statistics as stats
import requests
import sys
from .. import utils
import os
from dotenv import load_dotenv

load_dotenv()

THRESHOLD = 0.6


def prizepicks_cookie():
    cookie = os.environ.get('PRIZEPICKS_COOKIE')
    if not cookie:
        raise SystemExit(
            'PRIZEPICKS_COOKIE is not set. Copy the Cookie header from a logged-in '
            'request to api.prizepicks.com in DevTools and add it to .env'
        )
    return cookie


def prizepicks_headers():
    """Headers for projections fetch (document-style request)."""
    return {
        "accept": 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        "accept-language": 'en-US,en;q=0.6',
        "cache-control": 'max-age=0',
        "cookie": prizepicks_cookie(),
        "priority": 'u=0, i',
        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Brave";v="140"',
        "sec-ch-ua-mobile": '?0',
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": 'document',
        "sec-fetch-mode": 'navigate',
        "sec-fetch-site": 'none',
        "sec-fetch-user": '?1',
        "sec-gpc": '1',
        "upgrade-insecure-requests": '1',
        "user-agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    }

def main():
    global THRESHOLD
    utils.getArgs()

    # Get variables from utils
    SPORT = utils.SPORT
    api_stats = utils.api_stats
    pp_stats = utils.pp_stats
    league = utils.league
    offset = utils.offset
    start_day = utils.start_day
    end_day = utils.end_day

    if league == "MLB":
        THRESHOLD = 0
        
    # url = f'https://api.dailyfantasyapi.io/v1/lines/upcoming?sportsbook=PrizePicks&league={league}'
    # req = requests.get(url, headers= {
    #     'accept': 'application/json',
    #     'x-api-key': os.environ.get('DF_API_KEY')
    # })

    # data = req.content

    auto = True
    if len(sys.argv) >= 5:
        auto = False

    url = "https://api.prizepicks.com/projections"

    data = None
    # if graphical:
    #     options = webdriver.FirefoxOptions()
    #     options.add_argument('-headless')

    #     driver = webdriver.Firefox(options=options)
    #     ############## PRIZEPICKS ################################################

    #     driver.get(url)

    #     time.sleep(2)

    #     driver.find_element(By.ID, "rawdata-tab").click()

    #     time.sleep(2)

    #     data = driver.find_element(By.CLASS_NAME, "data").text
        
    #     driver.quit()
    if auto:
        req = requests.get(url, headers=prizepicks_headers())
        data = req.content
        print(req.status_code)
        if req.status_code != 200:
            print(f'Request failed w status {req.status_code}: {req.reason}')
            print(data)
            exit()
    else:
    # data = None
        current_directory = os.path.dirname(os.path.abspath(__file__))
        with open(f'{current_directory}/data.txt', 'r') as file:
            data = file.read()

    # Remove N/A stats
    filtered_pp_stats = [pp for pp in pp_stats if pp != "N/A"]
    api_stats = [api for pp, api in zip(pp_stats, api_stats) if pp != "N/A"]
    pp_stats = filtered_pp_stats

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

    events = utils.getEvents()

    for api_stat, pp_stat in zip(api_stats, pp_stats):
        for event in events:
            
            # NOTE: Price = the payout on a win, e.g 1.91x would be roughly -110 odds
            # EV: ((1/overPayout)*(line+0.5) + (1/underPayout)*(line-0.5)) / (1/overPayout + 1/underPayout)

            odds_json = utils.getEvent(event, api_stat)
            if odds_json != None:
                print('Number of events:', len(odds_json))

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
            if len(players[pp_stat][player]['otherBooks']) >= 3:
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

if __name__ == '__main__':
    main()