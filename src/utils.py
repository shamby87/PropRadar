from time import sleep
import pandas as pd
import numpy as np
import sys
import os
import requests
from discordwebhook import Discord  
from datetime import timedelta, datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.dirname(os.path.abspath(__file__))+'/../.env')
API_KEYS = os.environ.get('API_KEYS').split(',')
API_KEY_INDEX = 0
remainingRequests = 0

# The-odds-api.com
REGIONS = 'us' # uk | us | eu | au. Multiple can be specified if comma delimited
MARKETS = 'h2h' # h2h | spreads | totals. Multiple can be specified if comma delimited
ODDS_FORMAT = 'decimal' # decimal | american
DATE_FORMAT = 'iso' # iso | unix
RATE_LIMIT_SLEEP = 0.2 # seconds to wait after hitting rate limit

def getArgs():
    global SPORT, api_stats, sleeper_stats, pp_stats, league, offset, start_day, end_day
    if 'SPORT' in globals(): # only run once
        return    
    
    s = ""

    if len(sys.argv) >= 2:
        s = sys.argv[1]
    else:
        s = str(input("Which league? NFL, NBA, CBB, NHL, MLB: "))

    match s:
        case "NFL":
            SPORT = 'americanfootball_nfl' # use the sport_key from the /sports endpoint 
            api_stats = ['player_pass_yds', 'player_pass_completions', 'player_rush_yds', 'player_receptions', 'player_reception_yds', 'player_tds_over', 'player_pass_tds', 'player_rush_tds', 'player_reception_tds'] #The-odds-api
            pp_stats = ['Pass Yards', 'Pass Completions', 'Rush Yards', 'Receptions', 'Receiving Yards', '', '', '', ''] # Prizepicks
            sleeper_stats = ['passing_yards', 'pass_completions', 'rushing_yards', 'receptions', 'receiving_yards', 'anytime_touchdowns', 'passing_touchdowns', 'rushing_touchdowns', 'receiving_touchdowns'] # Sleeper
            league = "NFL"
        case "NBA":
            SPORT = 'basketball_nba' # use the sport_key from the /sports endpoint 
            api_stats = ['player_points', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists', 'player_rebounds_assists', 'player_assists', 'player_rebounds'] #The-odds-api
            pp_stats = ['Points', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts'] # Prizepicks
            sleeper_stats = ['points', 'pts_reb_ast', 'points_and_rebounds', 'points_and_assists', 'rebounds_and_assists', 'assists', 'rebounds'] # Sleeper
            league = "NBA"
        case "WNBA":
            SPORT = 'basketball_wnba' # use the sport_key from the /sports endpoint 
            api_stats = ['player_points', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists', 'player_rebounds_assists', 'player_assists', 'player_rebounds'] #The-odds-api
            pp_stats = ['Points', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts'] # Prizepicks
            sleeper_stats = ['points', 'pts_reb_ast', 'points_and_rebounds', 'points_and_assists', 'rebounds_and_assists', 'assists', 'rebounds'] # Sleeper
            league = "WNBA"
        case "CBB":
            SPORT = 'basketball_ncaab' # use the sport_key from the /sports endpoint 
            api_stats = ['player_points', 'player_assists', 'player_rebounds', 'player_points_rebounds_assists', 'player_points_rebounds', 'player_points_assists'] #The-odds-api
            pp_stats = ['Points', 'Assists', 'Rebounds', 'Pts+Rebs+Asts', 'Pts+Rebs', 'Pts+Asts'] # Prizepicks
            sleeper_stats = ['points', 'pts_reb_ast', 'points_and_rebounds', 'points_and_assists', 'rebounds_and_assists', 'assists', 'rebounds'] # Sleeper
            league = "CBB"
        case "NHL":
            SPORT = 'icehockey_nhl' # use the sport_key from the /sports endpoint 
            api_stats = ['player_shots_on_goal', 'player_points', 'player_total_saves'] #The-odds-api
            pp_stats = ['Shots on Goal', 'Points', 'Goalie Saves'] # Prizepicks
            sleeper_stats = ['shots', 'points', 'saves'] # Sleeper
            league = "NHL"
        case "MLB":
            SPORT = 'baseball_mlb' # use the sport_key from the /sports endpoint 
            api_stats = ['pitcher_strikeouts', 'pitcher_outs', 'pitcher_earned_runs', 'batter_hits', 'batter_total_bases', 'batter_hits_runs_rbis'] #The-odds-api
            pp_stats = ['Pitcher Strikeouts', 'Pitching Outs', 'N/A', 'N/A', 'N/A', 'N/A'] # Prizepicks
            sleeper_stats = ['strike_outs', 'outs', 'earned_runs', 'hits', 'total_bases', 'hits_runs_rbis'] # Sleeper
            league = "MLB"
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
            logMsg(f'Unknown stat: {s}', debug=True)
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
    global API_KEY_INDEX
    """
    Gets all the event IDs from the-odds-api.

    Returns a list containing all the IDs
    """

    odds_response = requests.get(
        f'https://api.the-odds-api.com/v4/sports/{SPORT}/odds',
        params={
            'api_key': API_KEYS[API_KEY_INDEX],
            'regions': REGIONS,
            'markets': MARKETS,
            'oddsFormat': ODDS_FORMAT,
            'dateFormat': DATE_FORMAT,
        }
    )

    events = []

    if odds_response.status_code != 200:
        if odds_response.json()["error_code"] == 'OUT_OF_USAGE_CREDITS':
            # Try to use the next API key and rerun
            API_KEY_INDEX += 1
            if API_KEY_INDEX < len(API_KEYS):
                return getEvents()
            else:
                logMsg('Out of API keys, exiting...', debug=True)
                exit()
        else:
            logMsg(f'Failed to get odds: status_code {odds_response.status_code}, response body {odds_response.json()}', debug=True)
            exit()
    else:
        odds_json = odds_response.json()
        # logMsg('Number of events:', len(odds_json))
        # logMsg(odds_json)

        for e in odds_json:
            event_date = datetime.fromisoformat(e['commence_time']) - timedelta(hours=offset)
            if event_date.date() >= start_day and event_date.date() <= end_day:
                events.append(e['id'])

        # Check the usage quota
        logMsg(f"Remaining requests {odds_response.headers['x-requests-remaining']}")
        # logMsg(f"Used requests {odds_response.headers['x-requests-used']}"")
    
    return events

def getEvent(eventID, market):
    global API_KEY_INDEX, remainingRequests
    """
    Function to get the details of a single event.

    eventID - The ID of the event, returned in the list from getEvents()
    market - The market parameter for the /odds endpoint. This will be the specific stat we want
    Returns: JSON string of the data returned from the endpoint, or None on failure
    """
    # sleep(0.2) # Make sure we dont make requests too fast
    response = requests.get(
        f'https://api.the-odds-api.com/v4/sports/{SPORT}/events/{eventID}/odds',
        params={
            'api_key': API_KEYS[API_KEY_INDEX],
            'regions': REGIONS,
            'markets': market,
            'oddsFormat': ODDS_FORMAT,
            'dateFormat': DATE_FORMAT,
        }
    )
    
    if response.status_code != 200:
        if response.json()["error_code"] == 'OUT_OF_USAGE_CREDITS':
            # Try to use the next API key and rerun
            API_KEY_INDEX += 1
            if API_KEY_INDEX < len(API_KEYS):
                return getEvent(eventID, market)
            else:
                logMsg('Out of API keys, exiting...', debug=True)
                exit()
        elif response.status_code == 429:
            logMsg(f'Rate limited. Waiting {RATE_LIMIT_SLEEP} seconds before retrying...')
            sleep(RATE_LIMIT_SLEEP)
            return getEvent(eventID, market)
        else:
            logMsg(f'Failed to get odds: status_code {response.status_code}, response body {response.json()}', debug=True)
            return None
    else:
        remainingRequests = int(response.headers['x-requests-remaining'])
        # Check the usage quota
        logMsg(f"Remaining requests {remainingRequests}")
        logMsg(f"Used requests {response.headers['x-requests-used']}")
        return response.json()


PARLAY_CHANNEL = Discord(url=os.environ.get('PARLAY_WEBHOOK'))
ADMIN_CHANNEL = Discord(url=os.environ.get('ADMIN_WEBHOOK'))
SLEEPER_PLAYS_CHANNEL = Discord(url=os.environ.get('SLEEPER_PLAYS_WEBHOOK'))
ADMIN = os.environ.get('ADMIN_ID')
SLEEPER = os.environ.get('SLEEPER_ROLE_ID')

def logMsg(text, sleeper=False, debug=False, notify=True, sleepPlays=False):
    now = datetime.now()
    dt_string = now.strftime("%m/%d/%Y %H:%M:%S")

    msg = f"{dt_string} - {text}"

    print(msg)
    if sleeper:
        PARLAY_CHANNEL.post(content=f'<@&{SLEEPER}> {text}')
    if debug:
        ADMIN_CHANNEL.post(content=f"{f'<@{ADMIN}> ' if notify else ''}{msg}")
    if sleepPlays:
        SLEEPER_PLAYS_CHANNEL.post(content=msg)

def getRemainingRequests():
    global API_KEY_INDEX, API_KEYS, remainingRequests
    return remainingRequests + ((len(API_KEYS) - (API_KEY_INDEX + 1)) * 500)
