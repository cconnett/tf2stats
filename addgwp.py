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

#coeffs = {
#    'kpm': 0.482795,
#    'dpm': -0.509169,
#    }
#coeffs = {
#    'kpm': 0.482795,
#    'dpm': -0.509169,
#    }
coeffs = {
    'kpm': 0.428550,
    'dpm': -0.103396,
    'teamgwp': 5.04946,
    'teamrf': 0.142656,
    'opprf': -0.696884,
}
coeffs = {
    'kpm': 0.45,
    'teamgwp': 1.0,
    'opprf': -0.18,
}


# Compute GWP
read.execute('select distinct pug, player, kpm, dpm, teamgwp, teamrf, opprf from playervitals')
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

# Compute Team and Opponent Team GWP
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

    read2.execute(team_query, (row['pug'], opposite[row['team']]))
    individualGWPs = [teammate['gwp'] for teammate in read2.fetchall()]
    while len(individualGWPs) < 5:
        individualGWPs.append(0.5)
    rawOppGWP = product(individualGWPs)

    teamGWP = rawTeamGWP / (rawTeamGWP + rawOppGWP)
    oppGWP = rawOppGWP / (rawTeamGWP + rawOppGWP)

    write.execute('update playervitals set teamgwp = ?, oppgwp = ? where pug = ? and team = ?',
                  (teamGWP, oppGWP, row['pug'], row['team']))
    print row['pug'], row['team']
conn.commit()
