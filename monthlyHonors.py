import sqlite3
from pprint import pprint

month = '2009-03'

conn = sqlite3.connect('/mnt/stash/tf2.db')
cursor = conn.cursor()

role_criteria = {
    'scout': ('pointcaptured', 'kill', 'kill assist'),
    'soldier': ('kill', 'killedobject', 'kill assist'),
    'pyro': ('kill', 'killedobject', 'kill assist'),
    'demoman': ('killedobject', 'kill', 'captureblocked'),
    'heavyweapons': ('kill', 'kill assist', 'killedobject'),
    'engineer': ('kill', 'killedobject', 'captureblocked', 'kill assist'),
    'medic': ('kill assist', 'chargedeployed', 'killobj assist', 'kill'),
    'sniper': ('kill', 'killedobject', 'kill assist', 'captureblocked'),
    'spy': ('kill', 'killedobject', 'killobj assist', 'captureblocked'),
    }


for (role, criteria) in role_criteria.items():
    print ('Top ' + role + ':').title(),

    roletops = []
    for criterion in criteria:
        cursor.execute("""
select p.name, e.type, count(*) as kills
 from events e
 join players p on e.srcplayer = p.steamid
 join lives l on e.srclife = l.id
 where e.type = ?

 and l.class = ?

 and e.time between datetime('%(month)s-01', 'start of month') and datetime('%(month)s-01', '1 month', '-1 second')

 group by p.name
 order by kills desc
 limit 4
 """ % locals(), (criterion, role))
        tops = cursor.fetchall()
        roletops.append(tops)
    criterion_toppers = set(name for (name, criterion, num) in
                            [top3[0] for top3 in roletops])
    if len(criterion_toppers) == 1:
        print list(criterion_toppers)[0]
    else:
        print
        for result in roletops:
            print ('  ' + role + ' ' + result[0][1] + 's').title()
            for (name, criterion, num) in result:
                print '    %32s %5d' % (name, num)
            print
