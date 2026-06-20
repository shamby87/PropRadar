import pandas as pd
import numpy as np
import json
from datetime import date
import statistics as stats
import requests
from .. import utils
import os

from .pp import prizepicks_headers

THRESHOLD = 0.6


def parse_goblin_players(raw, pp_stats, league, start_day, end_day):
    '''Parse PrizePicks projections JSON into goblin lines keyed by stat then player name.'''
    df = json.loads(raw) if isinstance(raw, str) else raw
    projections = pd.json_normalize(df['data'], max_level=3)
    included = pd.json_normalize(df['included'], max_level=3)
    inc_cop = included[included['type'] == 'new_player'].copy().dropna(axis=1)
    projections = pd.merge(
        projections,
        inc_cop,
        how='left',
        left_on=['relationships.new_player.data.id', 'relationships.new_player.data.type'],
        right_on=['id', 'type'],
        suffixes=('', '_new_player'),
    )
    filtered = projections.where(
        (projections['attributes.stat_type'].isin(pp_stats))
        & (projections['attributes.status'] == 'pre_game')
        & (projections['attributes.odds_type'] == 'goblin')
    )
    filtered = filtered[~filtered['attributes.stat_type'].isna()]

    players = {stat: {} for stat in pp_stats}
    for i in range(len(filtered)):
        player = filtered.iloc[i]
        desc = player['attributes.description']
        l = player['attributes.league']
        t = date.fromisoformat(player['attributes.start_time'].split('T')[0])
        if t < start_day or t > end_day:
            continue
        if (
            l == league
            and 'inning' not in desc.lower()
            and 'SZN' not in l
            and '1H' not in l
            and 'half' not in desc.lower()
            and 'combo' not in desc.lower()
            and 'first' not in desc.lower()
            and '1Q' not in desc
            and '4Q' not in desc
            and '4Q' not in l
        ):
            name = player['attributes.name'].lower()
            stat = player['attributes.stat_type']
            players[stat][name] = {
                'PPLine': player['attributes.line_score'],
                'otherBooks': [],
                'avgOdds': 0,
            }
    return players


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

    # Default: read pasted JSON from data.txt; pass --live to fetch from API
    url = "https://api.prizepicks.com/projections"

    if not utils.parse_args().live:
        current_directory = os.path.dirname(os.path.abspath(__file__))
        with open(f'{current_directory}/data.txt', 'r') as file:
            data = file.read()
    else:
        req = requests.get(url, headers=prizepicks_headers())
        data = req.content
        print(req.status_code)
        if req.status_code != 200:
            print(f'Request failed w status {req.status_code}: {req.reason}')
            print(data)
            exit()

    # Remove N/A stats
    filtered_pp_stats = [pp for pp in pp_stats if pp != "N/A"]
    api_stats = [f'{api}_alternate' for pp, api in zip(pp_stats, api_stats) if pp != "N/A"]
    pp_stats = filtered_pp_stats

    players = parse_goblin_players(data, pp_stats, league, start_day, end_day)

    events = utils.getEvents()

    for api_stat, pp_stat in zip(api_stats, pp_stats):
        for event in events:
            
            # NOTE: Price = the payout on a win, e.g 1.91x would be roughly -110 odds
            # EV: ((1/overPayout)*(line+0.5) + (1/underPayout)*(line-0.5)) / (1/overPayout + 1/underPayout)

            odds_json = utils.getEvent(event, api_stat)
            if odds_json != None:
                print('Number of events:', len(odds_json))

                for book in odds_json['bookmakers']:
                    for outcome in book['markets'][0]['outcomes']:
                        if outcome['name'] != "Over":
                            continue
                        name = outcome["description"].lower()
                        if not name in players[pp_stat]:
                            continue

                        # Just collect implied odds for the goblin line
                        if outcome['point'] != players[pp_stat][name]['PPLine']:
                            continue

                        impliedOdds = 1.0/outcome['price']
                        
                        players[pp_stat][name]['otherBooks'].append(impliedOdds)
            # exit()

        # After we get all the values from the books, find the avg and compare to the PPLine
        for player in players[pp_stat]:
            if len(players[pp_stat][player]['otherBooks']) >= 1:
                players[pp_stat][player]['avgOdds'] = stats.fmean(players[pp_stat][player]['otherBooks'])

    top_plays = {}
    # After all is done, print the top plays for each stat line
    for pp_stat in pp_stats:
        # Sort by greatest abs value
        print(f"{pp_stat}:")
        result = dict(sorted(players[pp_stat].items(), key=lambda item: item[1]['avgOdds'], reverse=True))

        num = min(6, len(result)) # Only print top 6 plays max
        for r in result.items():
            # if abs(r[1]['avgOdds']) < THRESHOLD: # Still want to show the first play no matter what, but once we hit shitty plays we should stop
            #     if num != min(6, len(result)):
            #         break
            if num > 0:
                print(f"\t{r[0]} - PPLine: {r[1]['PPLine']}, Avg Odds: {round(r[1]['avgOdds'], 4)*100}%, len: {len(r[1]['otherBooks'])}")
                # Add this play to our potential best parlay
                if r[0] not in top_plays:
                    top_plays[r[0]] = {'PPLine': r[1]['PPLine'], 'avgOdds': r[1]['avgOdds'], 'len': len(r[1]['otherBooks']), 'PPStat': pp_stat}
                elif top_plays[r[0]]['PPLine'] < r[1]['PPLine']: # Replace if they have a better dif in a different line
                    top_plays[r[0]] = {'PPLine': r[1]['PPLine'], 'avgOdds': r[1]['avgOdds'], 'len': len(r[1]['otherBooks']), 'PPStat': pp_stat}

            num -= 1

    # Print out the full best play
    result = dict(sorted(top_plays.items(), key=lambda item: item[1]['avgOdds'], reverse=True))
    num = min(6, len(result)) # Only print top 6 plays max
    print("\nFull best play:")
    for r in result.items():
        if num > 0:
            print(f"\t{r[0]} - PPLine: {r[1]['PPLine']} {r[1]['PPStat']}, Avg Odds: {round(r[1]['avgOdds'], 4)*100}%, len: {r[1]['len']}")

        num -= 1

if __name__ == '__main__':
    main()