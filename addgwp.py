import csv
import itertools
import math
import sqlite3
import operator

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))
def logit(p):
    return math.log(p/(1-p))

team_query = """select logit, coalesce(adjustment, 0.0) adjustment from pp
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

def computePlayerPerformance(conn):
    """Compute a player's raw performance based directly on their
    in-game stats.  Store the logit of this in the database."""
    read = conn.cursor()
    write = conn.cursor()

    read.execute('select distinct pug, player, kpm, dpm from playervitals')
    while True:
        row = read.fetchone()
        if row is None:
            break

        myLogit = 0
        for key in coeffs.keys():
            try:
                myLogit += coeffs[key] * float(row[key])
            except TypeError:
                pass

        write.execute('update playervitals set logit = ? where pug = ? and player = ?',
                      (myLogit, row['pug'], row['player']))
    conn.commit()

def computeTeamLogits(conn):
    """Sum the performance logits + adjustments of all the players on
    each team and store the values in the teamLogits table."""
    read = conn.cursor()
    read2 = conn.cursor()
    write = conn.cursor()

    read.execute('select distinct pug, team from playervitals')
    while True:
        row = read.fetchone()
        if row is None:
            break

        read2.execute(team_query, (row['pug'], row['team']))
        teamLogit = sum(teammate['logit'] + teammate['adjustment']
                        for teammate in read2.fetchall())

        write.execute('insert or replace into teamLogits values (?, ?, ?)',
                      (row['pug'], row['team'], teamLogit))
    conn.commit()

def updatePlayerAdjustments(conn, numPlayers=5):
    """Compute new adjustments to each players' raw performance logit
    by accounting for the average strength of their teammates and
    opponents."""
    read = conn.cursor()
    read2 = conn.cursor()
    write = conn.cursor()

    read.execute('select distinct pug, player, logit, coalesce(adjustment, 0.0) adjustment from playervitals')
    while True:
        row = read.fetchone()
        if row is None:
            break

        myLogit = row['logit'] + row['adjustment']
        read2.execute('''select count(*) nt, coalesce(avg(teamLogit), 0.0) from
        (select distinct pv.pug, pv.team, teamLogits.logit teamLogit
         from playervitals pv
         join teamLogits on teamLogits.pug = pv.pug and teamLogits.team = pv.team
         where player = ? and pv.pug != ?)''',
                      (row['player'], row['pug']))
        nt, avgTeamLogit, = read2.fetchone()
        read2.execute('''select count(*) no, coalesce(avg(oppLogit), 0.0) from
        (select distinct pv.pug, pv.team, teamLogits.logit oppLogit
         from playervitals pv
         join teams on teams.team = pv.team
         join teamLogits on teamLogits.pug = pv.pug and teamLogits.team = teams.opposite
         where player = ? and pv.pug != ?)''',
                      (row['player'], row['pug']))
        no, avgOppLogit, = read2.fetchone()

        if no >= 2:
            adjustment = avgOppLogit / numPlayers
        else:
            adjustment = 0.0

        write.execute('''update playervitals set avgTeamLogit = ?, avgOppLogit = ?, adjustment = ?
        where pug = ? and player = ?''',
                      (avgTeamLogit, avgOppLogit, adjustment, row['pug'], row['player']))
    conn.commit()

if __name__ == '__main__':
    conn = sqlite3.connect('/var/local/chris/pug.db')
    conn.row_factory = sqlite3.Row
    conn.create_function('sigmoid', 1, sigmoid)
    conn.create_function('logit', 1, logit)

    conn.executescript(file('setup.sql').read())
    conn.executescript(file('playercore.sql').read())

    # Compute player performance logit from core stats and model coeffs
    computePlayerPerformance(conn)

    # Compute actual Team Logits
    computeTeamLogits(conn)

    # Compute per player historical averages of team logit for teams
    # they were on and teams they opposed.  Store the adjustment value
    # to each player's own logit for the strength of their teammates
    # and opponents.
    updatePlayerAdjustments(conn)

    # Compute team logits again, this time using the latest
    # adjustments to players' logits.
    computeTeamLogits(conn)

    # Make the predictions
    read = conn.cursor()
    read.execute('''select teamLogits.logit teamLogit, oppLogits.logit oppLogit, win
    from playervitals pv
    join teams on teams.team = pv.team
    join teamLogits on teamLogits.pug = pv.pug and teamLogits.team = pv.team
    join teamLogits oppLogits on oppLogits.pug = pv.pug and oppLogits.team = teams.opposite''')

    n = 0
    correct = 0
    for row in read.fetchall():
        teamwp = sigmoid(row['teamLogit'] - row['oppLogit'])

        try:
            correct += bool(int(row['win'])) == (teamwp > 0.5)
        except TypeError:
            pass
        else:
            n += 1
    print '%s of %s correct = %.1f%%' % (correct, n, 100*float(correct) / n)
