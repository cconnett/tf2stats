import csv
import itertools
import math
import sqlite3
import operator

product = lambda seq: reduce(operator.mul, seq, 1)

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

team_query = """select gwp from pp
join playervitals pv on pv.pug = pp.pug and pv.player = pp.player
where class != 'medic' and pp.pug = ? and pp.team = ?
group by pp.pug, pp.player
order by sum(totaltime) desc
limit 5"""

opposite = {'Red': 'Blue', 'Blue': 'Red'}

conn = sqlite3.connect('/var/local/chris/pug.db')
conn.row_factory = sqlite3.Row
read = conn.cursor()
read2 = conn.cursor()
write = conn.cursor()
conn.executescript(file('setup.sql').read())
conn.executescript(file('playercore.sql').read())

coeffs = {
    'kpm': 0.482795,
    'dpm': -0.509169,
    }
coeffs = {
    'kpm': 0.310389,
    'dpm': -0.199889,
    'teamgwp': 1.80923,
    'oppgwp': -1.98867,
}

# Compute GWP
read.execute('select distinct pug, player, kpm, dpm, kdr, teamgwp, oppgwp from playervitals')
while True:
    row = read.fetchone()
    if row is None:
        break

    logit = 0
    for key in coeffs.keys():
        try:
            logit += coeffs[key] * float(row[key])
        except TypeError:
            pass

    write.execute('update playervitals set gwp = ? where pug = ? and player = ?',
                  (sigmoid(logit), row['pug'], row['player']))
    print row['pug'],row['player']
conn.commit()

# Compute actual Team GWPs
read.execute('select distinct pug, team from playervitals')
while True:
    row = read.fetchone()
    if row is None:
        break

    read2.execute(team_query, (row['pug'], row['team']))
    individualGWPs = [teammate['gwp'] for teammate in read2.fetchall()]
    while len(individualGWPs) < 5:
        individualGWPs.append(0.5)
    rawTeamGWP = product(individualGWPs)

    neutralGWP = (0.5)**len(individualGWPs)
    teamGWP = rawTeamGWP / (rawTeamGWP + neutralGWP)

    write.execute('insert or replace into teamGWPs values (?, ?, ?)',
                  (row['pug'], row['team'], teamGWP))
conn.commit()

# Compute player historical averages of Team GWP for teams they were
# on, and teams they opposed.
read.execute('select distinct pug, player from playervitals')
while True:
    row = read.fetchone()
    if row is None:
        break

    read2.execute('''select avg(gwp) from
    (select distinct pv.pug, pv.team, teamGWPs.gwp gwp
     from playervitals pv
     join teamGWPs on teamGWPs.pug = pv.pug and teamGWPs.team = pv.team
     where player = ? and pv.pug != ?)''',
                  (row['player'], row['pug']))
    teamGWP = read2.fetchone()[0]
    read2.execute('''select avg(gwp) from
    (select distinct pv.pug, pv.team, teamGWPs.gwp gwp
     from playervitals pv
     join teams on teams.team = pv.team
     join teamGWPs on teamGWPs.pug = pv.pug and teamGWPs.team = teams.opposite
     where player = ? and pv.pug != ?)''',
                  (row['player'], row['pug']))
    oppGWP = read2.fetchone()[0]
    write.execute('update playervitals set teamgwp = ?, oppgwp = ? where pug = ? and player = ?',
                  (teamGWP, oppGWP, row['pug'], row['player']))
    print row['pug'], row['player']
conn.commit()
