import sqlite3
import datetime
import respawnwaves
import attributedrow

def livingPlayers(team, time, round):
    """Return the number of each role that are alive for the given
    team at the given time.

    Returns a 4-tuple: (Scouts/Utilities, Soldiers, Demoman, Medic)
    """

    cursor.execute('''
    select player, team, class as role, begin as "begin [timestamp]" from lives
    where ? between lives.begin and lives.end
    and ? != lives.end
    and ? >= lives.spawn
    and team = ?
    and round = ?''', (time, time, time, team, round))
    lives = cursor.fetchall()

    count = [0,0,0,0]
    limits = [2,2,1,1]
    offclasses = 0

    for life in lives:
        try:
            count[{'scout': 0, 'soldier': 1,
                   'demoman': 2, 'medic': 3}[life.role]] += 1
        except KeyError:
            offclasses += 1

    #print count, offclasses
    for i in range(len(count)):
        utilitiesAssigned = min(offclasses, limits[i] - count[i])
        count[0] += utilitiesAssigned
        offclasses -= utilitiesAssigned

    return tuple(count)

def hasUber(team, time, round):
    """
    A fifth entry is 1 if the medic has been alive for 45 seconds (and
    should have uber).
    """

    cursor.execute('''select spawn as "spawn [timestamp]" from lives
    where class = 'medic' and team = ?
    and ? between begin and end and ? != end and round = ?''',
                (team, time, time, round))
    life = cursor.fetchone()

    cursor.execute('''select max(time) as "time [timestamp]" from events e
    join lives l on e.srclife = l.id
    where type = 3 and l.team = ? and time <= ? and e.round = ?''',
                (team, time, round))

    lastPop = cursor.fetchone()

    if life is None or life.spawn is None:
        return False
    if lastPop is None or lastPop.time is None:
        lastReset = life.spawn
    else:
        lastReset = max(life.spawn,
                        lastPop.time + datetime.timedelta(seconds=8))
    if (time - lastReset) >= datetime.timedelta(seconds=45):
        return True
    return False

def position(team, time, round):
    cursor.execute('''select midowner, point, humiliation, map from fights
    where ? between begin and end and ? != end and round = ?''',
                (time, time, round))
    fight = cursor.fetchone()
    if fight is None or fight.humiliation:
        return None
    return (map, fight.midowner, fight.point)

def wpStates(round):
    cursor.execute("""
    select time as 'time [timestamp]' from events where type in (5,11,3,9) and round = ?
    union
    select spawn from lives where spawn is not null and round = ?
    union
    select datetime(spawn, '45 seconds') from lives where class = 'medic' and round = ?
    and spawn is not null and datetime(spawn, '45 seconds') < end
    union
    select datetime(time, '53 seconds') from events
    where type = 3 and round = ? and datetime(time, '53 seconds') < (select end from rounds where id = ?)
    """, (round,round,round,round,round))
    times = [row.time for row in cursor.fetchall()]
    lastState = None

    for time in times:
        pos = position(None, time, round)
        if pos is None:
            break
        map, midowner, point = pos
        defender = {'Blue': 'Red', 'Red': 'Blue', None: None}[midowner]
        state = ((map, midowner, point),
                 livingPlayers(midowner or 'Blue', time, round), hasUber(midowner or 'Blue', time, round),
                 livingPlayers(defender or 'Red', time, round), hasUber(defender or 'Red', time, round))

        if state != lastState:
            yield state
        lastState = state

if __name__ == '__main__':
    conn = sqlite3.connect('/var/local/chris/pug.db',
                           detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = attributedrow.AttributedRow
    cursor = conn.cursor()

    cursor.execute("select distinct id from rounds where type = 'normal'")
    rounds = [row.id for row in cursor.fetchall()]

    stateRoundWP = collections.defaultdict(list)
    fightStates = []

    for r in rounds:
        cursor.execute('select winner from rounds where id = ?', (r,))
        winner = cursor.fetchone().winner
        for state in wpStates(r):
            stateRoundWP[state].append(winner)
        print 'Winner:', winner
