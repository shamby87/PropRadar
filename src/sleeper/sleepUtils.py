import json
import math
import os
import requests
from .. import utils
from dotenv import load_dotenv

load_dotenv()


class SleeperApiError(Exception):
    """Sleeper HTTP/JSON/GraphQL response could not be parsed or was invalid."""
    pass

def response_snippet(content, limit=200):
    if not content:
        return '<empty>'
    text = content.decode('utf-8', errors='replace') if isinstance(content, bytes) else str(content)
    return text if len(text) <= limit else text[:limit] + '...'


def parse_json_body(content, context):
    if content is None or (isinstance(content, (bytes, str)) and len(content) == 0):
        raise SleeperApiError(f'{context}: empty response')
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise SleeperApiError(
            f'{context}: invalid JSON ({e}); body: {response_snippet(content)}'
        ) from e


def parse_graphql_data(resp, context, *, require_status_200=True):
    if require_status_200 and resp.status_code != 200:
        raise SleeperApiError(
            f'{context}: HTTP {resp.status_code} {resp.reason}; body: {response_snippet(resp.content)}'
        )
    payload = parse_json_body(resp.content, context)
    errors = payload.get('errors')
    if errors:
        raise SleeperApiError(f'{context}: GraphQL errors {errors}')
    data = payload.get('data')
    if data is None:
        raise SleeperApiError(f'{context}: missing data field; body: {response_snippet(resp.content)}')
    return data


# Auth not really working, just copy cookie from real requests each time we need to use this
AUTH = os.environ.get('SLEEPER_AUTH')
URL = 'https://api.sleeper.app/graphql'

headers = {
    'accept': 'application/json',
    'Accept-Encoding':'gzip',
    'accept-language':'en',
    'authorization': AUTH,
    'baggage': 'sentry-environment=production,sentry-release=com.sleeperbot%40101.1,sentry-public_key=5337474302e74c13afa08fa99e908917,sentry-trace_id=78454af1c67b46db81ab288bc2a07524',
    'Connection': 'Keep-Alive',
    'Content-Type': 'application/json',
    'Host': 'api.sleeper.app',
    'sentry-trace': '78454af1c67b46db81ab288bc2a07524-9312f6e4eb2517e1',
    'User-Agent': 'okhttp/4.2.2',
    'x-amp-session': '1741133641253',
    'x-api-client': 'api.cached',
    'x-build': '101.1.v3643',
    'x-bundle': 'com.sleeperbot',
    'x-device-id': '27b6bfaf7c4ac4ff',
    'x-platform': 'android',
}

def getActivePromos():
    query = '#graphql\n        query list_eligible_promos($user_id: Snowflake!, $location: Location) {\n          list_eligible_promos(user_id: $user_id, location: $location) {\n            amount\n            available_at\n            created\n            expires_at\n            metadata\n            promo_id\n            type\n            user_id\n          }\n        }'
    graphql_op = 'list_eligible_promos'
    body = {
        "operationName": graphql_op,
        "query": query,
        "variables": {
            "user_id": "970139967005552640",
            "location": {
            "country": "US",
            "region": "MN"
            }
        }
    }

    header = headers.copy()
    header['Content-Length'] = str(len(query))
    header['x-sleeper-graphql-op'] = graphql_op

    session = requests.Session()
    resp = session.post(URL, headers=header, json=body)
    utils.logMsg(resp.content)
    return


def getPlayerPromos():
    '''
    Returns all active player promotions (discounts and payout boost)

    :returns: list of dictionaries with the following keys:
    - playerId (str)
    - type (str) Type of promo, either over_boost or line_discount
    - sport (str)
    - team (str)
    - stat (str)
    - lineId (str) ID used to place parlay with this promo
    - line (float)
    - payout (float)
    - ogLine (float)
    - ogPayout (float)
    - increase (float) % improvement over original value

    :returns: list of promo dicts on success, or None if promo data could not be loaded.
    '''
    # https://api.sleeper.app/lines/promos
    # Has promos that don't actually exist??
    ''' Combine with this (POST):
    https://api.sleeper.app/graphql
    {
        "operationName": "available_line_promotions",
        "query": "#graphql\n        query available_line_promotions($include_boosts: Boolean) {\n          available_line_promotions(include_boosts: $include_boosts) {\n            sport\n            season_type\n            season\n            game_id\n            subject_type\n            subject_id\n            wager_type\n            amount_limit\n            eligible_targets\n            type\n            expires_at\n          }\n        }",
        "variables": {
            "include_boosts": true
        }
    }
    Automatically excludes ones that have been used
    Example:
    {
        "amount_limit": 200,
        "eligible_targets": null,
        "expires_at": null,
        "game_id": "20250320_CBJ_FLA",
        "season": "2024",
        "season_type": "regular",
        "sport": "nhl",
        "subject_id": "1390",
        "subject_type": "player",
        "type": "over_boost",
        "wager_type": "saves"
      },
      {
        "amount_limit": 200,
        "eligible_targets": null,
        "expires_at": null,
        "game_id": "20250320_CBJ_FLA",
        "season": "2024",
        "season_type": "regular",
        "sport": "nhl",
        "subject_id": "1837",
        "subject_type": "player",
        "type": "line_discount",
        "wager_type": "saves"
      },
    '''
    res = []

    # Get active player promos
    query = '#graphql\n        query available_line_promotions($include_boosts: Boolean) {\n          available_line_promotions(include_boosts: $include_boosts) {\n            sport\n            season_type\n            season\n            game_id\n            subject_type\n            subject_id\n            wager_type\n            amount_limit\n            eligible_targets\n            type\n            expires_at\n          }\n        }'
    graphql_op = 'available_line_promotions'
    body = {
        "operationName": graphql_op,
        "query": query,
        "variables": {
            "include_boosts": True
        }
    }

    header = headers.copy()
    header['Content-Length'] = str(len(query))
    header['x-sleeper-graphql-op'] = graphql_op

    session = requests.Session()
    resp = session.post(URL, headers=header, json=body)
    try:
        data = parse_graphql_data(resp, 'available_line_promotions')
        linePromos = data['available_line_promotions']
    except SleeperApiError as e:
        utils.logMsg(str(e), debug=True)
        return None

    # Get all promos
    promoUrl = 'https://api.sleeper.app/lines/promos'
    resp = session.get(promoUrl)
    if resp.status_code != 200:
        utils.logMsg(
            f'lines/promos failed: HTTP {resp.status_code} {resp.reason}',
            debug=True,
        )
        return None
    try:
        allPromos = parse_json_body(resp.content, 'lines/promos')
    except SleeperApiError as e:
        utils.logMsg(str(e), debug=True)
        return None

    ogLines = {item['subject_id']: item for item in allPromos if item['line_type'] == 'normal'}
    allPromos = {item['subject_id']: item for item in allPromos if item['line_type'] != 'normal'}

    for promo in linePromos:
        id = promo['subject_id']
        if id not in allPromos or id not in ogLines:
            # Weird case, just skip it
            continue
        full = allPromos[id]['options'][0]
        fullOG = ogLines[id]['options'][0]
        type = promo['type']
        line = full['outcome_value']
        ogLine = fullOG['outcome_value']
        if promo['wager_type'] == 'outs' and (math.floor(line/3) == math.floor(ogLine/3)):
            # Same inning pitcher outs is a garbage discount, skip
            continue
        payout = float(full['payout_multiplier'])
        ogPayout = float(fullOG['payout_multiplier'])
        increase = 0
        if type == 'line_discount':
            increase = 1 - (line / ogLine)
        elif type == 'over_boost':
            increase = (payout / ogPayout) - 1
        res.append({
            'playerId': id,
            'type': type,
            'sport': promo['sport'],
            'team': full['subject_team'],
            'stat': promo['wager_type'],
            'lineId': full['line_id'],
            'line': line,
            'payout': payout,
            'ogLine': ogLine,
            'ogPayout': ogPayout,
            'increase': increase
        })
    
    res.sort(key=lambda x: x['increase'], reverse=True)
    return res

# Which sports have active lines: https://api.sleeper.app/lines/picks_sport_info?eg=22.control

def hasActiveLines(sport):
    url = 'https://api.sleeper.app/lines/picks_sport_info?eg=22.control'
    req = requests.get(url, timeout=30)
    if req.status_code != 200:
        utils.logMsg(
            f'hasActiveLines: HTTP {req.status_code} {req.reason}; body: {response_snippet(req.content)}',
            debug=True,
        )
        return False
    try:
        data = parse_json_body(req.content, 'picks_sport_info')
    except SleeperApiError as e:
        utils.logMsg(str(e), debug=True)
        return False

    entry = next((item for item in data if item.get('sport') == sport.lower()), None)
    if entry is None:
        utils.logMsg(f'hasActiveLines: no entry for sport {sport!r}', debug=True)
        return False
    return bool(entry.get('has_lines'))


def createParlay(lineIds, payoutMultiplier, amount=10, share=True):
    query = '#graphql\n            mutation create_parlay($type: String!, $currency_amount: Float!, $currency_type: String!, $league_id: String, $line_ids: [String]!, $league_public: Boolean!, $location: Location!, $promo_id: String, $prototype_parlay_id: String, $payout_version: String!, $client_max_payout: String, $entry_name: String, $vs_group: String, $client_possible_multipliers: Map, $boost_adjustment_version: String) {\n              create_parlay(type: $type, currency_amount: $currency_amount, currency_type: $currency_type, league_id: $league_id, line_ids: $line_ids, league_public: $league_public, location: $location, promo_id: $promo_id, prototype_parlay_id: $prototype_parlay_id, payout_version: $payout_version, client_max_payout: $client_max_payout, entry_name: $entry_name, vs_group: $vs_group, client_possible_multipliers: $client_possible_multipliers, boost_adjustment_version: $boost_adjustment_version) {\n                created\n                currency_amount\n                currency_type\n                league_id\n                legs {\n                  line {\n                    closed\n                    created\n                    game_id\n                    line_id\n                    outcome\n                    outcome_type\n                    outcome_value\n                    payout_multiplier\n                    season\n                    season_type\n                    score {\n                      date\n                      game_id\n                      metadata\n                      season\n                      season_type\n                      sport\n                      start_time\n                      status\n                      week\n                    }\n                    sport\n                    status\n                    subject\n                    subject_id\n                    subject_type\n                    valid_close_duration_seconds\n                    wager_type\n                    line_type\n                    metadata\n                  }\n                  line_id\n                  parlay_leg_id\n                  status\n                }\n                multiplier\n                parlay_id\n                status\n                user_id\n                display_data\n                graded_payout\n                graded_multiplier\n                graded_payout_boost\n                max_payout\n                max_multiplier\n                max_payout_boost\n                possible_multipliers {\n                  lost0\n                  lost1\n                  lost2\n                }\n              }\n            }'
    graphql_op = 'create_parlay'
    body = {
        "operationName": graphql_op,
        "query": query,
        "variables": {
            "type": "all in",
            "currency_amount": amount,
            "currency_type": "USD",
            "league_id": os.environ.get('SLEEPER_LEAGUE_ID') if share else None,
            "line_ids": lineIds,
            "league_public": True,
            "location": {
                "region": "MN",
                "country": "US",
                "longitude": -92.491676,
                "latitude": 44.060200
            },
            "promo_id": None,
            "payout_version": "dynamic.v4",
            "vs_group": "hep", # Not sure if this will work or if need to somehow generate it...
            "client_possible_multipliers": {
                "lost0": str(round(payoutMultiplier, 2))
            }
          }
    }

    header = headers.copy()
    header['Content-Length'] = str(len(query))
    header['x-sleeper-graphql-op'] = graphql_op

    session = requests.Session()
    resp = session.post(URL, headers=header, json=body)
    if resp.status_code != 200:
        utils.logMsg(f'Failed to create parlay {resp.status_code}: {resp.reason}', debug=True)
        return resp
    
    return resp

def getParlays(pending=False):
    graphql_op = 'my_parlays'
    query = '#graphql\n        query my_parlays($limit: Int, $offset: Int, $status_filter: [String], $include_pick_counts: Boolean) {\n          my_parlays(limit: $limit, offset: $offset, status_filter: $status_filter, include_pick_counts: $include_pick_counts) {\n            created\n            currency_amount\n            currency_type\n            league_id\n            legs {\n              line {\n                closed\n                created\n                game_id\n                line_id\n                metadata\n                outcome\n                outcome_type\n                outcome_value\n                payout_multiplier\n                season\n                season_type\n                score {\n                  date\n                  game_id\n                  metadata\n                  season\n                  season_type\n                  sport\n                  start_time\n                  status\n                  week\n                  total_views\n                }\n                sport\n                status\n                subject\n                subject_id\n                subject_type\n                valid_close_duration_seconds\n                wager_type\n                line_type\n                pick_count\n              }\n              line_id\n              parlay_leg_id\n              status\n              graded_at\n            }\n            multiplier\n            parlay_id\n            status\n            user_id\n            display_data\n            graded_payout\n            graded_multiplier\n            graded_payout_boost\n            graded_at\n            max_payout\n            max_multiplier\n            max_payout_boost\n            possible_multipliers {\n              lost0\n              lost1\n              lost2\n            }\n          }\n        }'
    
    header = headers.copy()
    header['Content-Length'] = str(len(query))
    header['x-sleeper-graphql-op'] = graphql_op

    status_filter = ["pending"] if pending else None

    body = {
        "operationName": graphql_op,
        "query": query,
        "variables": {
            "limit": 150,
            "offset": None,
            "status_filter": status_filter,
            "include_pick_counts": True
        }
    }

    session = requests.Session()
    resp = session.post(URL, headers=header, json=body)

    data = parse_graphql_data(resp, 'my_parlays')
    parlays = data.get('my_parlays')
    if parlays is None:
        raise SleeperApiError('my_parlays: field missing from response')
    return parlays

def postPlaysToDiscord(plays):
    if len(plays) == 0:
        return
    msg = "Valid plays for today:\n"
    for player in plays:
        msg += f"- **{player['name'].title()}** *{player['ou'].lower()}* {player['line']} {player['SleeperStat']} @ {player['payout']}x payout ({round((player['avgAdvantage']-1)*100,2)}% advantage)\n"

    utils.logMsg(msg, sleepPlays=True)

def generateShareLink(parlayId):
    return f'https://e.slpr.link/{parlayId}'

def shareParlayWithLeague(leagueId):
    pass
'''
Example share parlay with league:
queryql
  "operationName": "update_parlay",
  "query": "#graphql\n            mutation update_parlay($parlayId: Snowflake!, $leagueId: Snowflake) {\n              update_parlay(parlay_id: $parlayId, league_id: $leagueId) {\n                created\n                currency_amount\n                currency_type\n                league_id\n                legs {\n                  line {\n                    closed\n                    created\n                    game_id\n                    line_id\n                    outcome\n                    outcome_type\n                    outcome_value\n                    payout_multiplier\n                    season\n                    season_type\n                    score {\n                      date\n                      game_id\n                      metadata\n                      season\n                      season_type\n                      sport\n                      start_time\n                      status\n                      week\n                    }\n                    sport\n                    status\n                    subject\n                    subject_id\n                    subject_type\n                    valid_close_duration_seconds\n                    wager_type\n                    line_type\n                  }\n                  line_id\n                  parlay_leg_id\n                  status\n                }\n                multiplier\n                parlay_id\n                status\n                user_id\n                display_data\n                graded_payout\n                graded_multiplier\n                graded_payout_boost\n                max_payout\n                max_multiplier\n                max_payout_boost\n                possible_multipliers {\n                  lost0\n                  lost1\n                  lost2\n                }\n              }\n            }",
  "variables": {
    "parlayId": "1213264091859132416",
    "leagueId": "1212903614163451904"
  }
}
'''

'''
Example parlay:
queryql

{
  "operationName": "create_parlay",
  "query": "#graphql\n            mutation create_parlay($type: String!, $currency_amount: Float!, $currency_type: String!, $league_id: String, $line_ids: [String]!, $league_public: Boolean!, $location: Location!, $promo_id: String, $prototype_parlay_id: String, $payout_version: String!, $client_max_payout: String, $entry_name: String, $vs_group: String, $client_possible_multipliers: Map ) {\n              create_parlay(type: $type, currency_amount: $currency_amount, currency_type: $currency_type, league_id: $league_id, line_ids: $line_ids, league_public: $league_public, location: $location, promo_id: $promo_id, prototype_parlay_id: $prototype_parlay_id, payout_version: $payout_version, client_max_payout: $client_max_payout, entry_name: $entry_name, vs_group: $vs_group, client_possible_multipliers: $client_possible_multipliers) {\n                created\n                currency_amount\n                currency_type\n                league_id\n                legs {\n                  line {\n                    closed\n                    created\n                    game_id\n                    line_id\n                    outcome\n                    outcome_type\n                    outcome_value\n                    payout_multiplier\n                    season\n                    season_type\n                    score {\n                      date\n                      game_id\n                      metadata\n                      season\n                      season_type\n                      sport\n                      start_time\n                      status\n                      week\n                    }\n                    sport\n                    status\n                    subject\n                    subject_id\n                    subject_type\n                    valid_close_duration_seconds\n                    wager_type\n                    line_type\n                    metadata\n                  }\n                  line_id\n                  parlay_leg_id\n                  status\n                }\n                multiplier\n                parlay_id\n                status\n                user_id\n                display_data\n                graded_payout\n                graded_multiplier\n                graded_payout_boost\n                max_payout\n                max_multiplier\n                max_payout_boost\n                possible_multipliers {\n                  lost0\n                  lost1\n                  lost2\n                }\n              }\n            }",
  "variables": {
    "type": "all in",
    "currency_amount": 10,
    "currency_type": "USD",
    "league_id": null,
    "line_ids": [
      "1208543740881276962",
      "1208507638896148480"
    ],
    "league_public": true,
    "location": {
      "region": "CA",
      "country": "US",
      "longitude": -122.083922,
      "latitude": 37.4217937
    },
    "promo_id": null,
    "payout_version": "dynamic.v4",
    "client_possible_multipliers": {
      "lost0": "3.16"
    }
  }
}

Example parlay after everything changed to VS:

{
  "operationName": "create_parlay",
  "query": "#graphql\n            mutation create_parlay($type: String!, $currency_amount: Float!, $currency_type: String!, $league_id: String, $line_ids: [String]!, $league_public: Boolean!, $location: Location!, $promo_id: String, $prototype_parlay_id: String, $payout_version: String!, $client_max_payout: String, $entry_name: String, $vs_group: String, $client_possible_multipliers: Map, $boost_adjustment_version: String) {\n              create_parlay(type: $type, currency_amount: $currency_amount, currency_type: $currency_type, league_id: $league_id, line_ids: $line_ids, league_public: $league_public, location: $location, promo_id: $promo_id, prototype_parlay_id: $prototype_parlay_id, payout_version: $payout_version, client_max_payout: $client_max_payout, entry_name: $entry_name, vs_group: $vs_group, client_possible_multipliers: $client_possible_multipliers, boost_adjustment_version: $boost_adjustment_version) {\n                created\n                currency_amount\n                currency_type\n                league_id\n                legs {\n                  line {\n                    closed\n                    created\n                    game_id\n                    line_id\n                    outcome\n                    outcome_type\n                    outcome_value\n                    payout_multiplier\n                    season\n                    season_type\n                    score {\n                      date\n                      game_id\n                      metadata\n                      season\n                      season_type\n                      sport\n                      start_time\n                      status\n                      week\n                    }\n                    sport\n                    status\n                    subject\n                    subject_id\n                    subject_type\n                    valid_close_duration_seconds\n                    wager_type\n                    line_type\n                    metadata\n                  }\n                  line_id\n                  parlay_leg_id\n                  status\n                }\n                multiplier\n                parlay_id\n                status\n                user_id\n                display_data\n                graded_payout\n                graded_multiplier\n                graded_payout_boost\n                max_payout\n                max_multiplier\n                max_payout_boost\n                possible_multipliers {\n                  lost0\n                  lost1\n                  lost2\n                }\n              }\n            }",
  "variables": {
    "type": "all in",
    "currency_amount": 1,
    "currency_type": "USD",
    "league_id": null,
    "line_ids": [
      "1268963487875338256",
      "1269145988224794646"
    ],
    "league_public": true,
    "location": {
      "region": "CA",
      "country": "US",
      "longitude": -122.083922,
      "latitude": 37.4220936
    },
    "promo_id": null,
    "payout_version": "dynamic.v4",
    "vs_group": "hep",
    "client_possible_multipliers": {
      "lost0": "2.02"
    }
  }
}


need to fix location (set to 3516 19th ave):
"location": {
    "region": "MN",
    "country": "US",
    "longitude": -92.491676,
    "latitude": 44.060200
},

'''

def getBalance():
    '''
    :returns: USD balance as float, or None if the request or response could not be used.
    '''
    graphql_op = 'my_currencies'
    query = '#graphql\n        query my_currencies($withdrawableOnly: Boolean) {\n          my_currencies(withdrawable_only: $withdrawableOnly)\n        }'
    body = {
      "operationName": graphql_op,
      "query": query,
      "variables": {
        "withdrawableOnly": False
      }
    }

    header = headers.copy()
    header['Content-Length'] = str(len(query))
    header['x-sleeper-graphql-op'] = graphql_op

    session = requests.Session()
    try:
        resp = session.post(URL, headers=header, json=body, timeout=30)
    except requests.RequestException as e:
        utils.logMsg(f'getBalance: request failed ({e})', debug=True)
        return None

    try:
        data = parse_graphql_data(resp, 'my_currencies')
        currencies = data['my_currencies']
    except (SleeperApiError, KeyError, TypeError) as e:
        utils.logMsg(f'getBalance: {e}', debug=True)
        return None

    if 'USD' not in currencies:
        utils.logMsg(f'getBalance: USD missing (keys: {list(currencies.keys())})', debug=True)
        return None
    try:
        return float(currencies['USD'])
    except (TypeError, ValueError) as e:
        utils.logMsg(f'getBalance: invalid USD value ({e})', debug=True)
        return None

def getPlayerName(id, league):
    url = f'https://api.sleeper.app/players/{league}?exclude_injury=false'
    resp = requests.get(url)
    if resp.status_code != 200:
        utils.logMsg(f'Failed to get player id {id} for {league}. {resp.status_code}: {resp.reason}')
        return ''

    try:
        players = parse_json_body(resp.content, f'players/{league}')
        player = players[id]
    except SleeperApiError as e:
        utils.logMsg(str(e), debug=True)
        return ''
    except KeyError:
        utils.logMsg(f'getPlayerName: player {id} not in {league}', debug=True)
        return ''
    return f"{player['first_name']} {player['last_name']}"

if __name__ == '__main__':
    # getPlayerPromos()
    res = getParlays(True)
    pass