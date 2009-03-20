from pprint import pprint
import csv
import sqlite3

def recover_steamid(steamid):
    return steamid[1:].replace('_', ':')

if __name__ == '__main__':
    regression = csv.reader(open('skill.csv'))
    regression.next()
    regression.next()
    regression.next()
    regression.next()
    regression = list(regression)[:-1] # chop final blank line

    skills = [(float(coefficient), recover_steamid(steamid))
              for (steamid, coefficient, _, _, _) in regression
              if steamid.startswith('S')]
    skills.sort(reverse=True)

    conn = sqlite3.connect('/mnt/stash/tf2.db')
    cur = conn.cursor()

    for (i, (skill, steamid)) in enumerate(skills):
        cur.execute('select name from players where steamid = ?',
                    (steamid,))
        name = cur.fetchone()[0]
        print '%4d. %7.2f %s' % (i+1, float(skill)*1000, name.strip())
