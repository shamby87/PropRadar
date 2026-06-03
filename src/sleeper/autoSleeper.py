import json
import math
from time import sleep
from . import sleeper, sleepUtils
from .. import utils
import traceback

PROMO_THRESHOLD = 0.06 # Minimum increase to use player promo
PLAY_THRESHOLD = 1.02 # Minimum avgAdvantage to use play
MAX_PAYOUT = 2.15 # Don't want to use picks that are too unlikely to win
def placePlays():
    promos = [promo for promo in sleepUtils.getPlayerPromos() if (promo['increase'] >= PROMO_THRESHOLD and (promo['type'] == 'line_discount' or promo['ogPayout'] <= MAX_PAYOUT))]
    if len(promos) == 0:
        return
    utils.logMsg(promos, debug=True, notify=False)
    
    bestPlays = getBestAvailablePlays()
    balance = sleepUtils.getBalance()
    
    remainingPromos = len(promos)
    i = 0
    tried_swap = False
    while i < len(promos):
        if balance <= 0:
            utils.logMsg('Ran out of funds', debug=True)
            return
        
        promo = promos[i]
        wager = min(balance, 10)
        lineIds = [promo['lineId']]
        multiplier = promo['payout']
        parlay = [{
            'player': sleepUtils.getPlayerName(promo['playerId'], promo['sport']).title(),
            'stat': promo['stat'],
            'ou': 'over',
            'line': promo['line'],
            'payout': promo['payout']
        }]
        # Use 1-2 plays per promo, depending on how many good plays we still have to use
        parlaySize = min(2, math.ceil(len(bestPlays) / remainingPromos))
        for _ in range(parlaySize):
            index = 0
            if len(bestPlays) < index + 1:
                utils.logMsg('Out of plays')
                break
            
            nextPlay = bestPlays[index]
            while nextPlay['team'] == promo['team'] and nextPlay['sport'] == promo['sport']:
                index += 1
                if len(bestPlays) < index + 1:
                    utils.logMsg('Out of plays')
                    break
                nextPlay = bestPlays[index]
            
            if nextPlay['team'] == promo['team'] and nextPlay['sport'] == promo['sport']:
                break

            lineIds.append(nextPlay['lineId'])
            multiplier *= nextPlay['payout']
            parlay.append({
                'player': nextPlay['name'].title(),
                'stat': nextPlay['SleeperStat'],
                'ou': nextPlay['ou'].lower(),
                'line': nextPlay['line'],
                'payout': nextPlay['payout']
            })
            bestPlays.pop(index)

        if len(lineIds) == 1:
            if not tried_swap and i < len(promos) - 1 and len(bestPlays) > 0:
                promos[i], promos[i + 1] = promos[i + 1], promos[i]
                tried_swap = True
                continue
            utils.logMsg(f'Skipping promo (no filler leg): {parlay[0]["player"]} {parlay[0]["stat"]}', debug=True, notify=False)
            i += 1
            tried_swap = False
            continue

        multiplier = math.trunc(multiplier*100)/100
        res = sleepUtils.createParlay(lineIds, multiplier, wager)
        if res.status_code != 200:
            utils.logMsg(f'Create parlay status code {res.status_code}: {parlay}, content: {res.content}, reason: {res.reason}', debug=True)
            exit()
        content = json.loads(res.content)['data']
        if content['create_parlay'] == None:
            utils.logMsg(f'Failed to create parlay: {parlay}, content: {res.content}, reason: {res.reason}', debug=True)
        else:
            parlayMsg = '\n- *PROMO* '
            for idx, player in enumerate(parlay):
                if idx != 0:
                    parlayMsg += '- '
                parlayMsg += f"**{player['player']}** *{player['ou']}* {player['line']} {player['stat']} @ {player['payout']}x payout\n"
            parlayMsg += f'Overall Payout: **{multiplier}x**\n'
            parlayMsg += f'Copy this parlay: {sleepUtils.generateShareLink(content["create_parlay"]["parlay_id"])}'
            utils.logMsg(parlayMsg, sleeper=True)

            # Successful parlay creation, move on to next promo
            i += 1
            tried_swap = False
            balance -= wager
            remainingPromos -= 1
        sleep(10) # Sleep to prevent createParlay from failing for going too fast

    # if len(bestPlays) >= 2:
    #     nonPromoPlays(bestPlays)
    pass

def getBestAvailablePlays():
    '''
    Calls :func:`sleeper.getBestPlays()` to get best lines, removing any that are already in active parlays

    :returns: A list of dictionaries with the following keys:
    - name (str)
    - ou (str) Over/Under
    - line (float) The point value of the picked stat
    - lineId (str) The line ID to place parlay
    - playerId (str)
    - team (str)
    - SleeperStat (str) The stat to bet
    - payout (float)
    - avgAdvantage (float) How much better this payout is than the other books
    - len (int) How many books were considered
    - popularity (str) How many people made this pick (of the form "x/y = z%")
    - fitness (float)
    '''

    existingParlays = sleepUtils.getParlays(pending=True)
    existingPlayers = []
    for parlay in existingParlays:
        for leg in parlay['legs']:
            if leg['line']['metadata'].get('promotion', '') != 'true':
                existingPlayers.append(leg['line']['subject_id'])

    bestPlays = sleeper.getBestPlays()
    bestPlays = [{'name': key, **value} for key, value in bestPlays.items() if (value['avgAdvantage'] >= PLAY_THRESHOLD and value['payout'] <= MAX_PAYOUT and value['playerId'] not in existingPlayers)]
    sleepUtils.postPlaysToDiscord(bestPlays)
    
    return bestPlays

#TODO: Refactor this and placePlays() that use a ton of shared code
def nonPromoPlays(bestPlays=None):
    if bestPlays == None:
        bestPlays = getBestAvailablePlays()
    balance = sleepUtils.getBalance()
    #TODO: Use payout boost promos if available
    #TODO: Make more than just 2 leg parlays maybe

    parlaySize = 3
    while len(bestPlays) >= 2:
        i = 0
        if balance <= 0:
            utils.logMsg('Ran out of funds', debug=True)
            return
        
        play = bestPlays[i]
        wager = min(balance, 10)
        lineIds = [play['lineId']]
        multiplier = play['payout']
        parlay = [{
            'player': play['name'].title(),
            'stat': play['SleeperStat'],
            'ou': 'over',
            'line': play['line'],
            'payout': play['payout']
        }]
        bestPlays.pop(i)
        for _ in range(parlaySize-1):
            if len(bestPlays) < i + 1:
                utils.logMsg('Out of plays')
                break
            
            nextPlay = bestPlays[i]
            while nextPlay['team'] == play['team'] and nextPlay['sport'] == play['sport']:
                if len(bestPlays) < i + 1:
                    utils.logMsg('Out of plays')
                    break
                i += 1
                nextPlay = bestPlays[i]
            
            if nextPlay['team'] == play['team'] and nextPlay['sport'] == play['sport']:
                break

            lineIds.append(nextPlay['lineId'])
            multiplier *= nextPlay['payout']
            parlay.append({
                'player': nextPlay['name'].title(),
                'stat': nextPlay['SleeperStat'],
                'ou': nextPlay['ou'].lower(),
                'line': nextPlay['line'],
                'payout': nextPlay['payout']
            })
            bestPlays.pop(i)

        if len(lineIds) == 1:
            break

        multiplier = math.trunc(multiplier*100)/100
        res = sleepUtils.createParlay(lineIds, multiplier, wager)
        if res.status_code != 200:
            utils.logMsg(f'Create parlay status code {res.status_code}: {parlay}, content: {res.content}, reason: {res.reason}', debug=True)
            exit()
        content = json.loads(res.content)['data']
        if content['create_parlay'] == None:
            utils.logMsg(f'Failed to create parlay: {parlay}, content: {res.content}, reason: {res.reason}', debug=True)
        else:
            for player in parlay:
                parlayMsg += f"- **{player['player']}** *{player['ou']}* {player['line']} {player['stat']} @ {player['payout']}x payout\n"
            parlayMsg += f'Overall Payout: **{multiplier}x**\n'
            parlayMsg += f'Copy this parlay: {sleepUtils.generateShareLink(content["create_parlay"]["parlay_id"])}'
            utils.logMsg(parlayMsg, sleeper=True)

            balance -= wager
        sleep(10) # Sleep to prevent createParlay from failing for going too fast

    pass

if __name__ == '__main__':
    try:
        utils.getArgs()

        if sleepUtils.hasActiveLines(utils.league):
            placePlays()
            utils.logMsg(f'Done, remaining API requests: {utils.getRemainingRequests()}', debug=True, notify=False)
        else:
            utils.logMsg(f'No active games for {utils.league}', debug=True)
    except Exception as e:
        utils.logMsg(f'Failed to run autoSleeper: {traceback.format_exc()}', debug=True)
    
