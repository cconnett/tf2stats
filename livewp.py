import sqlite3
import datetime
import respawnwaves
import attributedrow

def livingPlayers(team, time, round, unspawnedDeaths):
    """Return the number of each role that are alive for the given
    team at the given time.

    Returns a 4-tuple: (Scouts/Utilities, Soldiers, Demoman, Medic)
    """

    deadPlayers = set(death.vicplayer for death in unspawnedDeaths)
    cur.execute(lives_query, (time, time, team, round))
    lives = cur.fetchall()
    lives = [life for life in lives if life.player not in deadPlayers]

    count = [0,0,0,0]
    limits = [2,2,1,1]
    offclasses = 0

    for life in lives:
        try:
            count[{'scout': 0, 'soldier': 1,
                   'demoman': 2, 'medic': 3}[life.role]] += 1
        except KeyError:
            offclasses += 1

        if life.role == 'medic' and \
           (time - life.begin) >= datetime.timedelta(seconds=45):
            uber = 1

    #print count, offclasses
    for i in range(len(count)):
        utilitiesAssigned = min(offclasses, limits[i] - count[i])
        count[0] += utilitiesAssigned
        offclasses -= utilitiesAssigned

    return tuple(count)

def hasUber(team, time, round, unspawnedDeaths):
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

    medicDeath = [death for death in unspawnedDeaths
                  if death.role == 'medic' and death.team == team]
    if life is None or medicDeath:
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
    cur.execute('''select midowner, point from fights
    where ? between begin and end and ? != end and round = ?''',
                (time, time, round))
    fight = cur.fetchone()
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
and team = ?
and round = ?
"""

round = 3
conn = sqlite3.connect('/var/local/chris/pug.db',
                       detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
conn.row_factory = attributedrow.AttributedRow
cur = conn.cursor()

cur.execute(deaths_query, (round,))
deaths = cur.fetchall()

cur.execute(fights_query, (round, ))
fights = cur.fetchall()

cur.execute('select end from rounds where id = ?', (round,))
roundEnd = cur.fetchone().end

wc = respawnwaves.WaveCalculator(deaths[0].time)

unspawnedDeaths = set()

theTime = deaths[0].time
while theTime < roundEnd:
    eventOccurred = False
    while deaths and deaths[0].time <= theTime:
        unspawnedDeaths.add(deaths[0])
        print '%s %s died at %s' % (deaths[0].team, deaths[0].role, deaths[0].time)
        eventOccurred = True
        del deaths[0]
    if fights and fights[0].end <= theTime:
        print '%s captured spire at %s.' % (fights[0].winner, theTime)
        eventOccurred = True
        wc.notifyOfCapture(fights[0])
        del fights[0]
    spawns = [death for death in unspawnedDeaths
              if wc.timeOfWave(death.team, wc.respawnWave(death)) <= theTime]
    for spawn in spawns:
        print '%s %s that died at %s respawns at %s' % (spawn.team, spawn.role, spawn.time, theTime)
        eventOccurred = True
    unspawnedDeaths -= set(spawns)
    for death in unspawnedDeaths:
        if eventOccurred:
            pass
        #    print '\t%s %s from %s (up at %s)' % (death.team, death.role, death.time,
        #                                          wc.timeOfWave(death.team, wc.respawnWave(death)))
    theTime += datetime.timedelta(seconds=1)
    if eventOccurred:
        print 'Blue:', livingPlayers('Blue', theTime, round, unspawnedDeaths), \
              hasUber('Blue', theTime, round, unspawnedDeaths)
        print 'Red: ', livingPlayers('Red', theTime, round, unspawnedDeaths), \
              hasUber('Red', theTime, round, unspawnedDeaths)
        print 'Position:', position(None, theTime, round)
        print
