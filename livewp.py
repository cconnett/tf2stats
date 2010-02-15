import sqlite3
import datetime
import respawnwaves
import attributedrow

conn = sqlite3.connect('/var/local/chris/pug.db',
                       detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
conn.row_factory = attributedrow.AttributedRow
cur = conn.cursor()

deaths_query = """
select vicplayer, viclife, lives.team as victeam, lives.class as role, time
from events join lives on events.viclife = lives.id
where type = 5 and events.round = ?
order by events.time, events.id"""
fights_query = """
select end as "end [timestamp]", winner, midowner, point
from fights
where round = ? and point in (4,5) and humiliation = 0
"""
nextFight_query = """
select end, winner, midowner, point
from fights
where round = ? and point in (4,5) and humiliation = 0
and end > ?
limit 1
"""

round = 3

cur.execute(deaths_query, (round,))
deaths = cur.fetchall()

cur.execute(fights_query, (round, ))
fights = cur.fetchall()

cur.execute('select end from rounds where id = ?', (round,))
roundEnd = cur.fetchone().end

wc = respawnwaves.WaveCalculator(deaths[0])

unspawnedDeaths = set()

theTime = deaths[0].time
while theTime < roundEnd:
    output = False
    while deaths and deaths[0].time <= theTime:
        unspawnedDeaths.add(deaths[0])
        print '%s %s died at %s' % (deaths[0].victeam, deaths[0].role, deaths[0].time)
        output = True
        del deaths[0]
    if fights and fights[0].end <= theTime:
        print '%s captured spire at %s.' % (fights[0].winner, theTime)
        output = True
        wc.notifyOfCapture(fights[0])
        del fights[0]
    spawns = [death for death in unspawnedDeaths
              if wc.timeOfWave(death.victeam, wc.respawnWave(death)) <= theTime]
    for spawn in spawns:
        print '%s %s that died at %s respawns at %s' % (spawn.victeam, spawn.role, spawn.time, theTime)
        output = True
    unspawnedDeaths -= set(spawns)
    for death in unspawnedDeaths:
        if output:
            print '\t%s %s from %s (up at %s)' % (death.victeam, death.role, death.time,
                                                  wc.timeOfWave(death.victeam, wc.respawnWave(death)))
    theTime += datetime.timedelta(seconds=1)
    if output: print
