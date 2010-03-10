import csv
import itertools
import math
import sqlite3

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

conn = sqlite3.connect('/var/local/chris/pug.db')
conn.row_factory = sqlite3.Row
read = conn.cursor()
write = conn.cursor()
#cursor.executescript(file('setup.sql').read())
#cursor.executescript(file('playercore.sql').read())

coeffs = {
    'kpm': 0.482795,
    'dpm': -0.509169,
    }

read.execute('select * from playervitals')

# Compute GWP
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

    write.execute('update playervitals set gwp = ? where round = ? and player = ?',
                  (sigmoid(logit), row['round'], row['player']))
    print row['round'],row['player']
conn.commit()
