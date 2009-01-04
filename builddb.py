from datetime import datetime
from pprint import pprint
from pyparsing import ParseException
from namedtuple import namedtuple
import logging
import sqlite3
import sys

from logparser import *

unparsedfilename = '/tmp/unparsed'
file(unparsedfilename, 'w').close() # Blank the file

class Round(object):
    __slots__ = ['id', 'map', 'miniround', 'type', 'point', 'series', 'begin', 'end', 'overtime', 'bluewin']
    def __init__(self, *args):
        for s,v in zip(Round.__slots__, args):
            setattr(self, s, v)

curround = Round(1, 'pl_goldrush', 'a', None, 1, 1, None, None, None, None)
curlives = {}
curteams = {}
curspecs = {}
lastkill = None
nextlife = 1
new_series = False

def processLogFile(filename, dbconn):
    global curround
    global curlives
    global curteams
    global curspecs
    global lastkill
    global nextlife
    global new_series

    cursor = dbconn.cursor()
    unparsed = file(unparsedfilename, 'a')

    for line in file(filename):
        try:
            result = logline.parseString(line)
        except ParseException:
            print >> unparsed, line
            continue

        timestamp = datetime.strptime(result.timestamp, '%m/%d/%Y - %H:%M:%S:')

        # New map: Here we can be sure that everything --- rounds and
        # lives --- are over.  Also record the map name locally.
        if result.loadmap:
            curround.map = result.loadmap.mapname
            curround.point = 1
            logging.info("***Loading map '%s'" % curround.map)
            curround.begin = timestamp
            curround.type = 'waiting'
            curround.miniround = 'a'
            curlives = {}
            curteams = {}

        # START OF ROUND TRACKING

        # Overtime started, record it.
        if result.overtime:
            curround.overtime = timestamp

        # Every "mini-round" (as the game logs call it) has a setup
        # phase, play phase with several points, and humiliation
        # phase.  E.g., on Goldrush, there are 3 mini-rounds: the
        # first two points, the second two points, and the last three
        # points each make up a mini-round.  We need to log all the
        # events at least from setup so that we know which engineers
        # get their stuff built up.  Might as well log humiliation for
        # posterity, since it'll be easy to filter it out.

        # (Note: I'm developing with logs from before the engineer
        # mini-update, so I don't know if there are any new events in
        # newer logs.  In my logs there are no mention of actual
        # teleport events, or teleporter or dispenser upgrades.)

        if result.setupbegin:
            curround.overtime = None
            curround.begin = timestamp
            curround.miniround = result.setupbegin.miniround.strip('"').strip('round_')
            curround.type = 'setup'

        if result.setupend:
            cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (curround.id, curround.map,
                            curround.miniround, 'setup',
                            None, curround.series,
                            curround.begin, timestamp, curround.overtime,
                            None))

            curround.id += 1
            curround.overtime = None
            curround.begin = timestamp
            curround.type = 'normal'

        if result.pointcaptured:
            # Record that the round is over and that blue won
            curround.end = timestamp
            cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (curround.id, curround.map,
                            curround.miniround, curround.type,
                            curround.point, curround.series,
                            curround.begin, timestamp, curround.overtime,
                            True))

            # Record the capturers
            for p in result.pointcaptured.keys():
                if p.startswith('player'):
                    player = actor.parseString(result.pointcaptured[p])
                    cursor.execute(
                "insert into events values (NULL, 'pointcaptured', ?, ?, ?, NULL, NULL, NULL, ?, NULL, NULL)",
                (timestamp, player.steamid, curlives[player.steamid][0], curround.id))

            curround.point += 1
            curround.id += 1
            curround.overtime = None
            curround.begin = timestamp
            curround.type = 'normal'

        if result.humiliationbegin:
            curround.begin = timestamp
            curround.overtime = None
            curround.bluewin = result.humiliationbegin.winner.strip('"') == 'Blue'
            curround.type = 'humiliation'

        if result.humiliationend:
            cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (curround.id, curround.map,
                            curround.miniround, curround.type,
                            None, curround.series,
                            curround.begin, timestamp, curround.overtime,
                            curround.bluewin))
            curround.id += 1
            if new_series:
                curround.series += 1
                curround.point = 1
                new_series = False

        if result.roundwin:
            # Round win: If blue won, we've already closed the round
            # and recorded the capture.  If red won, we now must close
            # the round.
            new_series = True

            if result.roundwin.winner.strip('"') == 'Red':
                cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                               (curround.id, curround.map,
                                curround.miniround, 'normal',
                                curround.point, curround.series,
                                curround.begin, timestamp, curround.overtime,
                                False))
                curround.id += 1
                curround.overtime = None

        # END OF ROUND TRACKING

        # START OF LIFE TRACKING

        # It should be pretty universal that spawns are at least 5
        # seconds, so don't record any lives that are 5 seconds or
        # shorter.

        if result.event:
            obj = None
            parent = None
            if result.kill or result.suicide:
                event = result.kill or result.suicide
                if result.kill:
                    eventtype = 'kill'
                    srcplayer = actor.parseString(event.killer).steamid
                    vicplayer = actor.parseString(event.victim).steamid
                elif result.suicide:
                    eventtype = 'suicide'
                    srcplayer = actor.parseString(event.suicider).steamid
                    vicplayer = actor.parseString(event.suicider).steamid

                weapon = event.weapon.strip('"')
                if event.customkill:
                    weapon = event.customkill.strip('"')

            elif result.triggered:
                event = result.triggered
                eventtype = event.eventname.strip('"')

                srcplayer = actor.parseString(event.srcplayer).steamid

                if eventtype in ['builtobject', 'killedobject']:
                    obj = event.object.strip('"').lower()

                if eventtype in ['killedobject']:
                    vicplayer = actor.parseString(event.objectowner).steamid
                elif eventtype in ['kill assist', 'domination', 'revenge']:
                    vicplayer = actor.parseString(event.vicplayer).steamid
                    parent = lastkill
                else:
                    vicplayer = None

                weapon = event.weapon.strip('"') if event.weapon else None

            srclife = curlives[srcplayer][0]
            viclife, curclass, nextclass, begin = curlives.get(vicplayer, (None,None,None,None))
            cursor.execute("insert into events values (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (eventtype, timestamp,
                            srcplayer, srclife,
                            vicplayer, viclife,
                            weapon, curround.id, parent, obj))
            if result.kill or result.suicide:
                end = timestamp
                lastkill = cursor.lastrowid
                cursor.execute("insert into lives values (?, ?, ?, ?, ?, ?, ?, ?)",
                               (viclife, vicplayer, curteams[vicplayer], curclass,
                                begin, end, eventtype, lastkill))
                curlives[vicplayer] = (nextlife, nextclass, nextclass, timestamp)
                nextlife += 1

        if result.changerole:
            newrole = result.changerole.newrole.strip('"')
            if result.changerole.steamid not in curlives:
                curlives[result.changerole.steamid] = (nextlife, newrole, newrole, timestamp)
                nextlife += 1
            curlife, curclass, nextclass, begin = curlives[result.changerole.steamid]
            curlives[result.changerole.steamid] = (curlife, curclass, newrole, begin)
        if result.changeteam:
            steamid = result.changeteam.steamid
            if result.changeteam.newteam in ['Red', 'Blue']:
                curteams[steamid] = result.changeteam.newteam.lower()
            if result.changeteam.team == 'Spectator':
                cursor.execute('insert into spectators values (?, ?, ?)',
                               (steamid, curspecs[steamid], timestamp))
            if result.changeteam.newteam == 'Spectator':
                curspecs[steamid] = timestamp
        if result.humiliationend:
            for steamid in curlives:
                non_death_end_life(cursor, steamid, curteams[steamid], timestamp, 'miniroundend')
                curlife, curclass, nextclass, begin = curlives[steamid]
                curlives[steamid] = (None, nextclass, nextclass, timestamp)
        if result.setupbegin:
            for steamid in curlives:
                curlife, curclass, nextclass, begin = curlives[steamid]
                curlives[steamid] = (nextlife, nextclass, nextclass, timestamp)
                nextlife += 1
        if result.leave:
                quitter = actor.parseString(result.leave.quitter)
                try:
                    non_death_end_life(cursor, quitter.steamid, quitter.team.lower(), timestamp, 'leaveserver')
                except KeyError, sqlite3.IntegrityError:
                    pass
                finally:
                    if quitter.steamid in curlives:
                        del curlives[quitter.steamid]

        # END OF LIFE TRACKING

        # Handle new players and name changes
        if result.enter or result.changename:
            if result.enter:
                newplayer = actor.parseString(result.enter.newplayer)
                steamid = newplayer.steamid
                name = newplayer.name
            elif result.changename:
                steamid = result.changename.steamid
                name = eval(result.changename.newplayer)
            cursor.execute('select count(name) from players where steamid = ?', (newplayer.steamid,))
            if cursor.fetchone()[0] == 0:
                cursor.execute('insert into players values (?, ?)',
                               (steamid, name))
            else:
                cursor.execute('update players set name = ? where steamid = ?',
                               (name, steamid))

def non_death_end_life(cursor, steamid, team, timestamp, reason):
    global curlives
    life, curclass, nextclass, begin = curlives[steamid]
    if life is not None:
        cursor.execute('insert into lives values (?, ?, ?, ?, ?, ?, ?, ?)',
                       (life, steamid, team, curclass, begin, timestamp, reason, None))

def deb(o):
    print str(type(o)) + ": " + repr(o)

def main(logs):
    dbconn = sqlite3.connect('tf2.db')
    for filename in logs:
        print 'Processing', filename
        processLogFile(filename, dbconn)
    dbconn.commit()
    dbconn.close()

if __name__ == '__main__':
    main(sys.argv[1:])
