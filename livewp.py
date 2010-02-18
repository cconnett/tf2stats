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
        count[i] += utilitiesAssigned
        offclasses -= utilitiesAssigned

    return tuple(count)

def hasUber(team, time, round):
    """
    Return 1 if the the medic for the given team should have uber.
    'Should have uber' is defined as alive for 45 seconds or more
    since his most recent pop or spawn.  Return 0 on no uber.
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
        return 0
    if lastPop is None or lastPop.time is None:
        lastReset = life.spawn
    elif (time - lastPop.time) <= datetime.timedelta(seconds=8):
        # If they're currently ubering, they obviously beat the 45
        # second estimate.  Make sure to count current ubers.
        return 1
    else:
        lastReset = max(life.spawn,
                        lastPop.time + datetime.timedelta(seconds=8))
    if (time - lastReset) >= datetime.timedelta(seconds=45):
        return 1
    return 0

def currentFight(team, time, round):
    cursor.execute('''select midowner, point, humiliation, map, winner from fights
    where ? between begin and end and ? != end and round = ?''',
                (time, time, round))
    fight = cursor.fetchone()
    if fight is None or fight.humiliation:
        return None
    return fight

def wpStates(round):
    cursor.execute("""
    select time as 'time [timestamp]' from events where type in (5,11,3,9) and round = ?
    union
    select spawn from lives where spawn is not null and round = ?
    union
    select datetime(spawn, '45 seconds') from lives where class = 'medic' and round = ?
    and spawn is not null and datetime(spawn, '45 seconds') < end
    union
    select datetime(time, '8 seconds') from events
    where type = 3 and round = ? and datetime(time, '53 seconds') < (select end from rounds where id = ?)
    union
    select datetime(time, '53 seconds') from events
    where type = 3 and round = ? and datetime(time, '53 seconds') < (select end from rounds where id = ?)
    """, (round,) * 7)
    times = [row.time for row in cursor.fetchall()]

    lastState = None

    for time in times:
        fight = currentFight(None, time, round)
        if fight is None:
            break
        defender = {'Blue': 'Red', 'Red': 'Blue', None: None}[fight.midowner]

        state = (fight.map, fight.midowner, fight.point) + \
                livingPlayers(fight.midowner or 'Blue', time, round) + \
                (hasUber(fight.midowner or 'Blue', time, round),) + \
                livingPlayers(defender or 'Red', time, round) + \
                (hasUber(defender or 'Red', time, round),) + \
                (fight.winner,)

        if state != lastState:
            yield state
        lastState = state

if __name__ == '__main__':
    conn = sqlite3.connect('/var/local/chris/pug.db',
                           detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    conn.row_factory = attributedrow.AttributedRow
    cursor = conn.cursor()

    statsfile = '/var/local/chris/wp.db'
    statsdb = sqlite3.connect(statsfile)

    sc = statsdb.cursor()
    sc.execute('''create table if not exists stats
    (map text, midowner text, point integer,
    o1 integer, o2 integer,
    o4 integer, o7 integer,
    oc boolean,
    d1 integer, d2 integer,
    d4 integer, d7 integer,
    dc boolean,
    fight_winner text, round_winner text)
    ''')
    sc.execute('delete from stats')
    cursor.execute("select distinct id from rounds where type = 'normal'")
    rounds = [row.id for row in cursor.fetchall()]

    insert = 'insert into stats values (' + ','.join(['?'] * 15) + ')'
    for r in rounds:
        print r
        cursor.execute('select winner from rounds where id = ?', (r,))
        winner = cursor.fetchone().winner
        for state in wpStates(r):
            sc.execute(insert, state + (winner,))
        print 'Winner:', winner
    statsdb.commit()
