from datetime import datetime
from pprint import pprint
from pyparsing import ParseException
from namedtuple import namedtuple
import logging
import sqlite3
import sys
import os

from logparser import *

unparsedfilename = '/tmp/unparsed-'
errorsfilename = '/tmp/errors-'
file(unparsedfilename, 'w').close() # Blank the file

class Round(object):
    __slots__ = ['id', 'map', 'miniround', 'type', 'point', 'series', 'begin', 'end', 'overtime', 'bluewin']
    def __init__(self, *args):
        for s,v in zip(Round.__slots__, args):
            setattr(self, s, v)

curround = Round(1, None, None, None, 1, 1, None, None, None, None)
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
    unparsed = file(unparsedfilename + os.path.basename(filename), 'a')
    errors = file(errorsfilename + os.path.basename(filename), 'a')
    errorcount = 0

    for line in file(filename):
        #print line
        try:
            result = logline.parseString(line)
        except ParseException:
            print >> unparsed, line
            continue
        timestamp = datetime.strptime(result.timestamp, '%m/%d/%Y - %H:%M:%S:')
        try:
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
                    elif eventtype in ['captureblocked', 'pointcaptured', 'chargedeployed']:
                        vicplayer = None
                    else:
                        # Some other event that we don't care about
                        # (e.g. "bm_autobalanceteams switch")
                        continue

                    weapon = event.weapon.strip('"') if event.weapon else None

                srclife = curlives[srcplayer][0]
                viclife, curclass, begin = curlives.get(vicplayer, (None,None,None))
                if srclife is not None:
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
                    curlives[vicplayer] = (nextlife, curclass, timestamp)
                    nextlife += 1

            if result.changerole:
                steamid = result.changerole.steamid
                newrole = result.changerole.newrole.strip('"')
                if steamid in curlives:
                    non_death_end_life(cursor, steamid, curteams[steamid], timestamp, 'changerole')
                curlives[steamid] = (nextlife, newrole, timestamp)
                nextlife += 1
            if result.changeteam:
                steamid = result.changeteam.steamid
                if result.changeteam.newteam in ['Red', 'Blue']:
                    curteams[steamid] = result.changeteam.newteam.lower()
                if result.changeteam.team == 'Spectator':
                    cursor.execute('insert into spectators values (?, ?, ?)',
                                   (steamid, curspecs[steamid], timestamp))
                    del curspecs[steamid]
                if result.changeteam.newteam == 'Spectator':
                    curspecs[steamid] = timestamp
            if result.humiliationend:
                for steamid in curlives:
                    non_death_end_life(cursor, steamid, curteams[steamid], timestamp, 'miniroundend')
                    curlife, curclass, begin = curlives[steamid]
                    curlives[steamid] = (None, curclass, timestamp)
            if result.setupbegin:
                for steamid in curlives:
                    curlife, curclass, begin = curlives[steamid]
                    curlives[steamid] = (nextlife, curclass, timestamp)
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

                    if quitter.team == 'Spectator':
                        cursor.execute('insert into spectators values (?, ?, ?)',
                                       (quitter.steamid, curspecs[quitter.steamid], timestamp))
                    if quitter.steamid in curspecs:
                        del curspecs[quitter.steamid]
                    if quitter.steamid in curteams:
                        del curteams[quitter.steamid]

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
        except Exception, e:
            print >> errors, e
            print >> errors, line
            errorcount += 1
    # Clean out the meaningless entries in spectators
    cursor.execute('delete from spectators where begin = end')
    # Clean out lives of 0 seconds
    cursor.execute('delete from lives where begin = end')
    return errorcount

def non_death_end_life(cursor, steamid, team, end, reason):
    global curlives
    life, curclass, begin = curlives[steamid]
    if life is not None and begin != end:
        cursor.execute('insert into lives values (?, ?, ?, ?, ?, ?, ?, ?)',
                       (life, steamid, team, curclass, begin, end, reason, None))

def deb(o):
    print str(type(o)) + ": " + repr(o)

def main(logs):
    dbconn = sqlite3.connect('tf2.db')
    for filename in logs:
        print 'Processing', filename,
        errorcount = processLogFile(filename, dbconn)
        if errorcount != 0:
            print 'errors = %d' % errorcount
        else:
            print
    #dbconn.commit()
    dbconn.close()

if __name__ == '__main__':
    main(sys.argv[1:])
