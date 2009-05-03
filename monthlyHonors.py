import sqlite3
from pprint import pprint
import collections
import math

POWER = math.log(3) / math.log(2)

month = '2009-03'

conn = sqlite3.connect('/mnt/stash/tf2.db')
cursor = conn.cursor()

main_query = """
select p.steamid, r.series, count(*) as number
 from events e
 join players p on e.srcplayer = p.steamid
 join lives l on e.srclife = l.id
 join rounds r on e.round = r.id
 where e.type = ?

 and r.type = 'normal'

 and l.class = ?

 and e.time between datetime('%(month)s-01', 'start of month') and datetime('%(month)s-01', '1 month', '-1 second')

 group by p.steamid, r.series
 """ % locals()

weapon_query = """
select p.steamid, r.series, count(*) as number
 from events e
 join players p on e.srcplayer = p.steamid
 join lives l on e.srclife = l.id
 join rounds r on e.round = r.id
 where e.type = ?

 and r.type = 'normal'

 and l.class = ?
 and e.weapon = ?

 and e.time between datetime('%(month)s-01', 'start of month') and datetime('%(month)s-01', '1 month', '-1 second')

 group by p.steamid, r.series
""" % locals()

victim_query = """
select p.steamid, r.series, count(*) as number
 from events e
 join players p on e.srcplayer = p.steamid
 join lives l on e.srclife = l.id
 join rounds r on e.round = r.id
 where e.type = ?

 and r.type = 'normal'

 and l.class = ?
 and (select victim.class from lives victim where e.viclife = victim.id) = ?

 and e.time between datetime('%(month)s-01', 'start of month') and datetime('%(month)s-01', '1 month', '-1 second')

 group by p.steamid, r.series
""" % locals()

roles = ['scout', 'soldier', 'pyro',
         'demoman', 'heavyweapons', 'engineer',
         'medic', 'sniper', 'spy']

def role_honor_scores(role):
    event_values = [(main_query, ('kill', role), 1),
                    (main_query, ('kill assist', role), 0.5),
                    (main_query, ('pointcaptured', role), 2),
                    (main_query, ('captureblocked', role), 1),
                    (main_query, ('killedobject', role), 1),
                    (main_query, ('killobj assist', role), 1),
                    (main_query, ('revenge', role), 1),
                    ]

    if role == 'medic':
        event_values.append((main_query, ('chargedeployed', role), 1))

        event_values.remove((main_query, ('kill assist', role), 0.5))
        event_values.append((main_query, ('kill assist', role), 1))
    #if role == 'engineer':
    #    event_values.append((main_query, ('player_teleported', role), 0.5))
    if role == 'scout':
        event_values.append((victim_query, ('kill', role, 'medic'), 1))

        event_values.remove((main_query, ('pointcaptured', role), 2))
        event_values.append((main_query, ('pointcaptured', role), 4))
    if role == 'sniper':
        event_values.append((weapon_query, ('kill', role, 'headshot'), 1))
    if role == 'spy':
        event_values.append((weapon_query, ('kill', role, 'backstab'), 1))

    tally = collections.defaultdict(float)

    for (query, subs, value) in event_values:
        #print 'executing', subs, 'got',
        cursor.execute(query, subs)
        data = cursor.fetchall()
        #print len(data)
        for (steamid, series, number) in data:
            tally[(steamid, series)] += value * number

    #pprint(tally)

    finalscores = collections.defaultdict(float)
    for ((steamid, series), valve_points) in tally.items():
        finalscores[steamid] += valve_points ** POWER

    return finalscores

for role in roles:
    scores = role_honor_scores(role)
    scores = [(score, steamid) for (steamid, score) in scores.items()]
    scores.sort(reverse=True)

    print ('Top ' + role + ':').title(),
    print
    for (score, steamid) in scores[:4]:
        cursor.execute('select name from players where steamid = ?', (steamid,))
        (name,) = cursor.fetchone()
        print '    %32s %8.2f' % (name, score)
