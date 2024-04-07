import pandas as pd
import numpy as np
import sys
import os
import requests
from datetime import timedelta, datetime, timezone
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get('API_KEY')

# The-odds-api.com
REGIONS = 'us' # uk | us | eu | au. Multiple can be specified if comma delimited
MARKETS = 'h2h' # h2h | spreads | totals. Multiple can be specified if comma delimited
ODDS_FORMAT = 'decimal' # decimal | american
DATE_FORMAT = 'iso' # iso | unix

def getArgs():
    global SPORT, api_stats, sleeper_stats, pp_stats, league, offset, start_day, end_day
    s = ""

    if len(sys.argv) >= 2:
        s = sys.argv[1]
    else:
        s = str(input("Which league? NFL, NBA, CBB, NHL, MLB: "))

    match s:
        case "NFL":
            SPORT = 'americanfootball_nfl' # use the sport_key from the /sports endpoint 
            api_stats = ['player_pass_yds', 'player_pass_completions', 'player_rush_yds', 'player_receptions', 'player_reception_yds'] #The-odds-api
            pp_stats = ['Pass Yards', 'Pass Completions', 'Rush Yards', 'Receptions', 'Receiving Yards'] # Prizepicks
            sleeper_stats = ['Pass Yards', 'Pass Completions', 'Rush Yards', 'Receptions', 'Receiving Yards'] # Sleeper
            league = "nfl"
        case "NBA":
            SPORT = 'basketball_nba' # use the sport_key from the /sports endpoint 
            api_stats = ['player_points', 'player_assists', 'player_rebounds', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists', 'player_rebounds_assists'] #The-odds-api
            pp_stats = ['Points', 'Assists', 'Rebounds', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts', 'Rebs+Asts'] # Prizepicks
            sleeper_stats = ['points', 'assists', 'rebounds', 'pts_reb_ast', 'points_and_rebounds', 'points_and_assists', 'rebounds_and_assists'] # Sleeper
            league = "nba"
        case "CBB":
            SPORT = 'basketball_ncaab' # use the sport_key from the /sports endpoint 
            api_stats = ['player_points', 'player_assists', 'player_rebounds', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists'] #The-odds-api
            pp_stats = ['Points', 'Assists', 'Rebounds', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts'] # Prizepicks
            sleeper_stats = ['Points', 'Assists', 'Rebounds', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts'] # Sleeper
            league = "cbb"
        case "NHL":
            SPORT = 'icehockey_nhl' # use the sport_key from the /sports endpoint 
            api_stats = ['player_shots_on_goal', 'player_points', 'player_total_saves'] #The-odds-api
            pp_stats = ['Shots on Goal', 'Points', 'Goalie Saves'] # Prizepicks
            sleeper_stats = ['Shots on Goal', 'Points', 'Goalie Saves'] # Sleeper
            league = "nhl"
        case "MLB":
            SPORT = 'baseball_mlb' # use the sport_key from the /sports endpoint 
            api_stats = ['pitcher_strikeouts', 'pitcher_outs'] #The-odds-api
            pp_stats = ['Pitcher Strikeouts', 'Pitching Outs'] # Prizepicks
            sleeper_stats = ['Pitcher Strikeouts', 'Pitching Outs'] # Sleeper
            league = "mlb"
        # Bunch of old single stat stuff, legacy but still want it just in case
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

    offset = 5 # CDT
    start_day = datetime.now(timezone(-timedelta(hours=offset))).date() + timedelta(days=start_d) # Needed to convert to CST
    end_day = datetime.now(timezone(-timedelta(hours=offset))).date() + timedelta(days=end_d) 

def getEvents():
    """
    Gets all the event IDs from the-odds-api.

    Returns a list containing all the IDs
    """

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
    
    return events

def getEvent(eventID, market):
    """
    Function to get the details of a single event.

    eventID - The ID of the event, returned in the list from getEvents()
    market - The market parameter for the /odds endpoint. This will be the specific stat we want
    Returns: JSON string of the data returned from the endpoint, or None on failure
    """
    event_test = requests.get(
            f'https://api.the-odds-api.com/v4/sports/{SPORT}/events/{eventID}/odds',
            params={
                'api_key': API_KEY,
                'regions': REGIONS,
                'markets': market,
                'oddsFormat': ODDS_FORMAT,
                'dateFormat': DATE_FORMAT,
            }
        )
    
    if event_test.status_code != 200:
        print(f'Failed to get odds: status_code {event_test.status_code}, response body {event_test.text}')
        return None
    else:
        # Check the usage quota
        print('Remaining requests', event_test.headers['x-requests-remaining'])
        print('Used requests', event_test.headers['x-requests-used'])
        
        return event_test.json()


