import math
from time import sleep
from . import sleeper, sleepUtils
from .. import utils
import traceback

PROMO_THRESHOLD = 0.06  # Minimum increase to use player promo
PLAY_THRESHOLD = 1.02  # Minimum avgAdvantage to use play
MAX_PAYOUT = 2.15  # Don't want to use picks that are too unlikely to win
WAGER_CAP = 10
PARLAY_SUBMIT_SLEEP = 10


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

    rawPlays = sleeper.getBestPlays()
    if rawPlays is None:
        utils.logMsg(
            f'getBestAvailablePlays: no lines for {utils.league} in date range',
            debug=True,
            notify=False,
        )
        return []

    bestPlays = [
        {'name': key, **value}
        for key, value in rawPlays.items()
        if value['avgAdvantage'] >= PLAY_THRESHOLD
        and value['payout'] <= MAX_PAYOUT
        and value['playerId'] not in existingPlayers
    ]
    sleepUtils.postPlaysToDiscord(bestPlays)

    return bestPlays


def play_to_leg(play):
    return {
        'player': play['name'].title(),
        'stat': play['SleeperStat'],
        'ou': play['ou'].lower(),
        'line': play['line'],
        'payout': play['payout'],
    }


def promo_to_leg(promo):
    return {
        'player': sleepUtils.getPlayerName(promo['playerId'], promo['sport']).title(),
        'stat': promo['stat'],
        'ou': 'over',
        'line': promo['line'],
        'payout': promo['payout'],
    }


def find_next_play_index(available_plays, team, sport):
    '''Index of the best play that is not on the same team and sport (required for 2-leg parlays).'''
    if len(available_plays) == 0:
        utils.logMsg('Out of plays')
        return None
    index = 0
    while available_plays[index]['team'] == team and available_plays[index]['sport'] == sport:
        index += 1
        if len(available_plays) <= index:
            utils.logMsg('Out of plays')
            return None
    return index


def build_parlay(first_leg, first_line_id, first_payout, team, sport, available_plays, num_extra_plays):
    '''
    Build a parlay starting with one leg, then attach up to num_extra_plays from available_plays.
    The 2nd leg must not share team + sport with the first; 3rd leg and beyond have no such restriction.
    '''
    lineIds = [first_line_id]
    multiplier = first_payout
    parlay = [first_leg]
    for leg_num in range(num_extra_plays):
        if leg_num == 0:
            index = find_next_play_index(available_plays, team, sport)
        elif len(available_plays) == 0:
            utils.logMsg('Out of plays')
            index = None
        else:
            index = 0
        if index is None:
            break
        play = available_plays[index]
        lineIds.append(play['lineId'])
        multiplier *= play['payout']
        parlay.append(play_to_leg(play))
        available_plays.pop(index)
    return lineIds, multiplier, parlay


def format_parlay_message(parlay, multiplier, parlay_id, *, promo=False):
    msg = '\n- *PROMO* ' if promo else '- '
    for idx, player in enumerate(parlay):
        if idx != 0:
            msg += '- '
        msg += (
            f"**{player['player']}** *{player['ou']}* {player['line']} "
            f"{player['stat']} @ {player['payout']}x payout\n"
        )
    msg += f'Overall Payout: **{multiplier}x**\n'
    msg += f'Copy this parlay: {sleepUtils.generateShareLink(parlay_id)}'
    return msg


def try_create_parlay(lineIds, multiplier, wager, parlay, *, promo=False, dry_run=False):
    '''
    Submit a parlay to Sleeper. Returns True on success.
    '''
    multiplier = math.trunc(multiplier * 100) / 100
    if dry_run:
        utils.logMsg(format_parlay_message(parlay, multiplier, "dry_run", promo=promo))
        return True

    res = sleepUtils.createParlay(lineIds, multiplier, wager)
    if res.status_code != 200:
        utils.logMsg(
            f'Create parlay HTTP {res.status_code}: {parlay}, reason: {res.reason}, '
            f'body: {sleepUtils.response_snippet(res.content)}',
            debug=True,
        )
        return False

    try:
        content = sleepUtils.parse_graphql_data(res, 'create_parlay', require_status_200=False)
    except sleepUtils.SleeperApiError as e:
        utils.logMsg(f'Create parlay response error: {e}; attempted: {parlay}', debug=True)
        return False

    if content['create_parlay'] is None:
        utils.logMsg(
            f'Failed to create parlay: {parlay}, content: {res.content}, reason: {res.reason}',
            debug=True,
        )
        return False

    parlay_id = content['create_parlay']['parlay_id']
    utils.logMsg(format_parlay_message(parlay, multiplier, parlay_id, promo=promo), sleeper=True)
    return True


def placePlays(*, dry_run=False):
    promos_raw = sleepUtils.getPlayerPromos()
    if promos_raw is None:
        utils.logMsg('placePlays: failed to fetch promos; aborting', debug=True)
        return
    promos = [
        promo for promo in promos_raw
        if promo['increase'] >= PROMO_THRESHOLD
        and (promo['type'] == 'line_discount' or promo['ogPayout'] <= MAX_PAYOUT)
    ]
    if len(promos) == 0:
        return
    utils.logMsg(promos, debug=True, notify=False)

    try:
        bestPlays = getBestAvailablePlays()
    except Exception as e:
        utils.logMsg(f'placePlays: {e}; aborting', debug=True)
        return
    if len(bestPlays) == 0:
        utils.logMsg('placePlays: no best plays available; aborting', debug=True, notify=False)
        return
    balance = sleepUtils.getBalance()
    if balance is None or balance <= 0:
        utils.logMsg('placePlays: no funds available; aborting', debug=True)
        return

    remainingPromos = len(promos)
    i = 0
    tried_swap = False
    while i < len(promos):
        if balance <= 0:
            utils.logMsg('Ran out of funds', debug=True)
            return

        promo = promos[i]
        wager = min(balance, WAGER_CAP)

        # Use 1-2 plays per promo, depending on how many good plays we still have to use
        plays_to_add = min(2, math.ceil(len(bestPlays) / remainingPromos))
        lineIds, multiplier, parlay = build_parlay(
            promo_to_leg(promo),
            promo['lineId'],
            promo['payout'],
            promo['team'],
            promo['sport'],
            bestPlays,
            plays_to_add,
        )

        if len(lineIds) == 1:
            if not tried_swap and i < len(promos) - 1 and len(bestPlays) > 0:
                promos[i], promos[i + 1] = promos[i + 1], promos[i]
                tried_swap = True
                continue
            utils.logMsg(
                f'Skipping promo (no compatible best play): {parlay[0]["player"]} {parlay[0]["stat"]}',
                debug=True,
                notify=False,
            )
            i += 1
            tried_swap = False
            continue

        if try_create_parlay(lineIds, multiplier, wager, parlay, promo=True, dry_run=dry_run):
            i += 1
            tried_swap = False
            balance -= wager
            remainingPromos -= 1
        if not dry_run:
            sleep(PARLAY_SUBMIT_SLEEP)  # Sleep to prevent createParlay from failing for going too fast

    # if len(bestPlays) >= 2:
    #     nonPromoPlays(bestPlays)


def nonPromoPlays(bestPlays=None, *, dry_run=False):
    if bestPlays is None:
        try:
            bestPlays = getBestAvailablePlays()
        except Exception as e:
            utils.logMsg(f'nonPromoPlays: {e}; aborting', debug=True)
            return
    balance = sleepUtils.getBalance()
    if balance is None or balance <= 0:
        utils.logMsg('nonPromoPlays: no funds available; aborting', debug=True)
        return

    # TODO: Use payout boost promos if available
    # TODO: Make more than just 2 leg parlays maybe
    while len(bestPlays) >= 2:
        parlaySize = min(3, len(bestPlays))
        if balance <= 0:
            utils.logMsg('Ran out of funds', debug=True)
            return

        play = bestPlays.pop(0)
        wager = min(balance, WAGER_CAP)
        lineIds, multiplier, parlay = build_parlay(
            play_to_leg(play),
            play['lineId'],
            play['payout'],
            play['team'],
            play['sport'],
            bestPlays,
            parlaySize - 1,
        )

        if len(lineIds) == 1:
            break

        if try_create_parlay(lineIds, multiplier, wager, parlay, promo=False, dry_run=dry_run):
            balance -= wager
        if not dry_run:
            sleep(PARLAY_SUBMIT_SLEEP)  # Sleep to prevent createParlay from failing for going too fast


if __name__ == '__main__':
    try:
        utils.getArgs()
        dry_run = utils.parse_args().dry_run
        if dry_run:
            utils.logMsg('DRY RUN enabled — parlays will be logged but not submitted')
        placePlays(dry_run=dry_run)
        utils.logMsg(
            f'Done, remaining API requests: {utils.getRemainingRequests()}',
            debug=True,
            notify=False,
        )
    except Exception:
        utils.logMsg(f'autoSleeper failed: {traceback.format_exc()}', debug=True)
