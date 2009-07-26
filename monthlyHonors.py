# -*- Encoding: utf-8 -*-

import sqlite3
from pprint import pprint
import collections
import math
from cStringIO import StringIO
import codecs
import sys

debug = False

POWER = math.log(3) / math.log(2)

month = '2009-06'

conn = sqlite3.connect('/mnt/stash/tf2.db')
cursor = conn.cursor()

honor_titles = {'scout': 'Swiftest Scout',
                'soldier': 'Soldier of Valor',
                'pyro': 'Fire Marshal',
                'demoman': 'Demolition Expert',
                'heavyweapons': 'Heroic Heavy',
                'engineer': 'Chief Engineer',
                'medic': u'Überlegen Arzt',
                'sniper': 'Elite Marksman',
                'spy': 'Master of Disguise',
                }

# need ordering, so can't use honors_titles.keys()
roles = ['scout', 'soldier', 'pyro',
         'demoman', 'heavyweapons', 'engineer',
         'medic', 'sniper', 'spy'
    ]

main_query = """
select p.steamid, r.series, r.miniround, count(*) as number
 from events e
 join players p on e.srcplayer = p.steamid
 join lives l on e.srclife = l.id
 join rounds r on e.round = r.id
 where e.type = ?

 and r.type = 'normal'

 and l.class = ?

 and e.time between datetime('%(month)s-01', 'start of month') and datetime('%(month)s-01', '1 month', '-1 second')

 group by p.steamid, r.series, r.miniround
 """ % locals()

weapon_query = """
select p.steamid, r.series, r.miniround, count(*) as number
 from events e
 join players p on e.srcplayer = p.steamid
 join lives l on e.srclife = l.id
 join rounds r on e.round = r.id
 where e.type = ?

 and r.type = 'normal'

 and l.class = ?
 and e.weapon = ?

 and e.time between datetime('%(month)s-01', 'start of month') and datetime('%(month)s-01', '1 month', '-1 second')

 group by p.steamid, r.series, r.miniround
""" % locals()

victim_query = """
select p.steamid, r.series, r.miniround, count(*) as number
 from events e
 join players p on e.srcplayer = p.steamid
 join lives l on e.srclife = l.id
 join rounds r on e.round = r.id
 where e.type = ?

 and r.type = 'normal'

 and l.class = ?
 and (select victim.class from lives victim where e.viclife = victim.id) = ?

 and e.time between datetime('%(month)s-01', 'start of month') and datetime('%(month)s-01', '1 month', '-1 second')

 group by p.steamid, r.series, r.miniround
""" % locals()

def role_honor_scores(role):
    event_values = [(main_query, (5, role), 1), #kill
                    (main_query, (6, role), 0.5), #kill assist
                    (main_query, (9, role), 2), #pointcaptured
                    (main_query, (2, role), 1), #captureblocked
                    (main_query, (7, role), 1), #killedobject
                    (main_query, (8, role), 1), #killedobject assist
                    (main_query, (10, role), 1), #revenge
                    ]

    if role == 'medic':
        event_values.append((main_query, (3, role), 1)) #chargedeployed

        event_values.remove((main_query, (6, role), 0.5))
        event_values.append((main_query, (6, role), 1))
    #if role == 'engineer':
    #    event_values.append((main_query, ('player_teleported', role), 0.5))
    if role == 'scout':
        event_values.append((victim_query, (5, role, 'medic'), 1))

        event_values.remove((main_query, (9, role), 2))
        event_values.append((main_query, (9, role), 4))
    if role == 'sniper':
        event_values.append((weapon_query, (5, role, 'headshot'), 1))
    if role == 'spy':
        event_values.append((weapon_query, (5, role, 'backstab'), 1))

    tally = collections.defaultdict(float)

    for (query, subs, value) in event_values:
        if debug:
            print 'executing', subs, 'got',
        cursor.execute(query, subs)
        data = cursor.fetchall()
        if debug:
            print len(data)
        for (steamid, series, miniround, number) in data:
            series = str(series) + miniround
            tally[(steamid, series)] += value * number

    #pprint(tally)

    finalscores = collections.defaultdict(float)
    for ((steamid, series), valve_points) in tally.items():
        finalscores[steamid] += valve_points ** POWER

    return finalscores


forum_post = StringIO()
top_scores = []
winners = set()

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
        top_scores.append((score, role, steamid))

honors = dict.fromkeys(honor_titles.keys(), None)
top_scores.sort(reverse=True)
for (score, role, steamid) in top_scores:
    if honors[role] is None and steamid not in winners:
        honors[role] = steamid
        winners.add(steamid)
assert None not in honors.values()

for role in roles:
    steamid = honors[role]
    cursor.execute('select name from players where steamid = ?', (steamid,))
    (name,) = cursor.fetchone()
    print '[b]' + honor_titles[role] + ':[/b] ' + name + '\n'

