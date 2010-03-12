import csv
import itertools
import math
import sqlite3
import operator

product = lambda seq: reduce(operator.mul, seq, 1)

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))
def logit(p):
    return math.log(p/(1-p))

def removePlayerGWP(teamGWP, playerGWP, numPlayers=5):
    g = teamGWP
    p = playerGWP
    n = numPlayers
    x = g / (2**n * (1-g) * p)
    return x / (2**(1-n) + x)

team_query = """select gwp from pp
join playervitals pv on pv.pug = pp.pug and pv.player = pp.player
where class != 'medic' and pp.pug = ? and pp.team = ?
group by pp.pug, pp.player
order by sum(totaltime) desc
limit 5"""

opposite = {'Red': 'Blue', 'Blue': 'Red'}

coeffs = {
    'kpm': 0.623747,
    'dpm': -0.656491,
    }

def computePlayerGWP(conn):
    read.execute('select distinct pug, player, kpm, dpm, teamgwp, oppgwp from playervitals')
    while True:
        row = read.fetchone()
        if row is None:
            break

        l = 0
        for key in coeffs.keys():
            try:
                l += coeffs[key] * float(row[key])
            except TypeError:
                pass

        write.execute('update playervitals set gwp = ? where pug = ? and player = ?',
                      (sigmoid(l), row['pug'], row['player']))
    conn.commit()

def computeTeamGWP(conn):
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


if __name__ == '__main__':
    conn = sqlite3.connect('/var/local/chris/pug.db')
    conn.row_factory = sqlite3.Row
    conn.create_function('sigmoid', 1, sigmoid)
    conn.create_function('logit', 1, logit)
    conn.create_function('removePlayerGWP', 2, removePlayerGWP)

    read = conn.cursor()
    read2 = conn.cursor()
    write = conn.cursor()
    conn.executescript(file('setup.sql').read())
    conn.executescript(file('playercore.sql').read())

    # Compute GWP from core stats and model coeffs
    computePlayerGWP(conn)

    # Compute actual Team GWPs
    computeTeamGWP(conn)

    # Compute player historical averages of Team GWP for teams they
    # were on, and teams they opposed.  Adjust each player's own GWP
    # for the strength of their teammates and opponents.
    read.execute('select distinct pug, player, gwp from playervitals')
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

        adjustment = None
        if teamGWP is not None and oppGWP is not None:
            adjustment = -logit(removePlayerGWP(teamGWP, row['gwp'])) + logit(oppGWP)

        write.execute('''update playervitals set teamgwp = ?, oppgwp = ?, adjustment = ?, gwp = ?
        where pug = ? and player = ?''',
                      (teamGWP, oppGWP, adjustment, sigmoid(logit(row['gwp']) + (adjustment or 0.0)),
                       row['pug'], row['player']))
    conn.commit()

    # Compute Team GWPs again, this time using adjusted player GWPs
    computeTeamGWP(conn)

    # Make the predictions
    read.execute('''select teamGWPs.gwp teamwp, oppGWPs.gwp oppwp, win
    from playervitals pv
    join teams on teams.team = pv.team
    join teamGWPs on teamGWPs.pug = pv.pug and teamGWPs.team = pv.team
    join teamGWPs oppGWPs on oppGWPs.pug = pv.pug and oppGWPs.team = teams.opposite''')

    n = 0
    correct = 0
    for row in read.fetchall():
        teamwp = row['teamwp'] / (row['teamwp'] + row['oppwp'])

        try:
            correct += bool(int(row['win'])) == (teamwp > 0.5)
        except TypeError:
            pass
        else:
            n += 1
    conn.commit()
    print '%s of %s correct = %.1f%%' % (correct, n, 100*float(correct) / n)
