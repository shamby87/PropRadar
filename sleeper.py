import requests
import pandas as pd
import numpy as np
import json
import statistics as stats
import utils

def fitness(player):
    """
    Gives a value to quantify how good a given pick is. Weighted combination of 
    popularity and average advantage over other sportsbooks
    """
    



def main():
    utils.getArgs()

    # Variables for fitness calculaton
    popWeight = .33
    advWeight = .67
    
    # Get variables from utils
    api_stats = utils.api_stats
    sleeper_stats = utils.sleeper_stats
    league = utils.league.lower()
    start_day = utils.start_day
    end_day = utils.end_day

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
        
        totalPicks = float(player['pick_stats.counts.total'])
        overPop = float(player['pick_stats.counts.over'])
        underPop = float(player['pick_stats.counts.under'])
        for option in player['options']:
            players[stat][name][option['outcome']] = { # 'Outcome' is over or under
                'line': option['outcome_value'],
                'payout': float(option['payout_multiplier']),
                'otherBooks': [],
                'otherLines': [],
                'avgAdvantage': 0,
                'stdev': 0,
                # 'popularity': f"{overPop if option['outcome'] == 'over' else underPop}/{totalPicks} = " + str(round(float(player[f"pick_stats.counts.{option['outcome']}"]) / totalPicks * 100, 2)) + "%" # popularity score from 0 to 1 (e.g how many overs vs how many total picks) 
                'pop': overPop if option['outcome'] == 'over' else underPop
            }

    maxPop = max(option['pop']  for stat in players.values()
                                for p in stat.values()
                                for option in p.values()
                 )
    # print(json.dumps(players, indent=2))

    events = utils.getEvents()

    for api_stat, sleeper_stat in zip(api_stats, sleeper_stats):
        for event in events:
            odds_json = utils.getEvent(event, api_stat)
            if odds_json != None:
                print('Number of events:', len(odds_json))

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
        maxAdv = 0
        for player in players[sleeper_stat]:
            for outcome in ['over', 'under']:
                if len(players[sleeper_stat][player][outcome]['otherBooks']) > 1:
                    # A ratio > 1 means this payout is 'avgAdvantage' times greater than average across other books
                    adv = players[sleeper_stat][player][outcome]['payout'] / stats.fmean(players[sleeper_stat][player][outcome]['otherBooks'])
                    players[sleeper_stat][player][outcome]['avgAdvantage'] = adv
                    if adv > maxAdv:
                        maxAdv = adv
                    # players[sleeper_stat][player][outcome]['stdev'] = stats.stdev(players[sleeper_stat][player][outcome]['otherBooks'])

    # Calculate the fitness for every pick
    for sleeper_stat in sleeper_stats:
        for player in players[sleeper_stat]:
            for outcome in ['over', 'under']:
                # Scale the popularity and the avgAdv to be between 0 and 1, then take weighted combo of both
                popScale = players[sleeper_stat][player][outcome]['pop'] / maxPop 
                advScale = players[sleeper_stat][player][outcome]['avgAdvantage'] / maxAdv 
                
                players[sleeper_stat][player][outcome]['fitness'] = popWeight*popScale + advWeight*advScale

    top_plays = {}
    # After all is done, print the top plays for each stat line
    for sleeper_stat in sleeper_stats:
        # Sort by greatest fitness, only look at better of over/under for each player 
        print(f"{sleeper_stat}:")
        result = dict(sorted(players[sleeper_stat].items(), key=lambda item: max(item[1]['over']['fitness'], item[1]['under']['fitness']), reverse=True))

        num = min(6, len(result)) # Only print top 6 plays max
        for r in result.items():
            if num > 0:
                info = r[1]['over'] if r[1]['over']['fitness'] >= r[1]['under']['fitness'] else r[1]['under']
                ou = "Over" if r[1]['over']['fitness'] >= r[1]['under']['fitness'] else "Under"
                
                print(f"\t{r[0]} - line: {ou} {info['line']}, avg advantage: {round(info['avgAdvantage'], 4)}, len: {len(info['otherBooks'])}, popularity: {info['popularity']}, fitness: {info['fitness']}")
                
                # Add this play to our potential best parlay
                top_plays[r[0]] = {'ou': ou, 'payout': info['payout'], 'line': info['line'], 'avgAdvantage': info['avgAdvantage'], 'len': len(info['otherBooks']), 'popularity': info['popularity'], 'SleeperStat': sleeper_stat, 'fitness': info['fitness']}
            num -= 1

    # Print out the full best play
    result = dict(sorted(top_plays.items(), key=lambda item: item[1]['fitness'], reverse=True))
    num = min(6, len(result)) # Only print top 6 plays max
    print("\nFull best play:")
    for r in result.items():
        if num > 0:
            print(f"\t{r[0]} - line: {r[1]['ou']} {r[1]['line']} {r[1]['SleeperStat']}, payout: {r[1]['payout']}x, avg advantage: {round(r[1]['avgAdvantage'], 4)}, len: {r[1]['len']}, popularity: {r[1]['popularity']}, fitness: {r[1]['fitness']}")

        num -= 1

if __name__ == '__main__':
    main()