import sqlite3
import datetime
import respawnwaves
import attributedrow

def livingPlayers(team, time, round):
    """Return the number of each role that are alive for the given
    team at the given time.

    Returns a 4-tuple: (Scouts/Utilities, Soldiers, Demoman, Medic)
    """

    cur.execute(lives_query, (time, time, time, team, round))
    lives = cur.fetchall()

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

    cur.execute('''select spawn as "spawn [timestamp]" from lives
    where class = 'medic' and team = ?
    and ? between begin and end and ? != end and round = ?''',
                (team, time, time, round))
    life = cur.fetchone()

    cur.execute('''select max(time) as "time [timestamp]" from events e
    join lives l on e.srclife = l.id
    where type = 3 and l.team = ? and time <= ? and e.round = ?''',
                (team, time, round))

    lastPop = cur.fetchone()

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
    cur.execute('''select midowner, point, humiliation from fights
    where ? between begin and end and ? != end and round = ?''',
                (time, time, round))
    fight = cur.fetchone()
    if fight.humiliation:
        return None
    return (fight.midowner, fight.point)

deaths_query = """
select vicplayer, viclife, lives.team, lives.class as role, time
from events join lives on events.viclife = lives.id
where type = 5 and events.round = ?
order by events.time, events.id"""
fights_query = """
select end as "end [timestamp]", winner, midowner, point
from fights
where round = ? and point in (4,5)
and humiliation = 0
"""
lives_query = """
select player, team, class as role, begin as "begin [timestamp]" from lives
where ? between lives.begin and lives.end
and ? != lives.end
and ? >= lives.spawn
and team = ?
and round = ?
"""

round = 3
conn = sqlite3.connect('/var/local/chris/pug.db',
                       detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
conn.row_factory = attributedrow.AttributedRow
cur = conn.cursor()

statechange_query = """
select time as 'time [timestamp]' from events where type in (5,11,3,9) and round = ?
union
select spawn from lives where spawn is not null and round = ?
union
select datetime(spawn, '45 seconds') from lives where class = 'medic' and round = ?
and spawn is not null and datetime(spawn, '45 seconds') < end
union
select datetime(time, '53 seconds') from events
where type = 3 and round = ? and datetime(time, '53 seconds') < (select end from rounds where id = ?)
"""

cur.execute(statechange_query, (round,round,round,round,round))
times = [row.time for row in cur.fetchall()]

for theTime in times:
    print theTime
    print 'Blue:', livingPlayers('Blue', theTime, round), \
          hasUber('Blue', theTime, round)
    print 'Red: ', livingPlayers('Red', theTime, round), \
          hasUber('Red', theTime, round)
    print
