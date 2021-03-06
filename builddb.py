from datetime import datetime
from pprint import pprint
from pyparsing import ParseException
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
lastkilledobject = None
lastkillassist = None
nextlife = 1

event_types = {}
object_types = {}

def processLogFile(filename, dbconn):
    global curround
    global curlives
    global curteams
    global curspecs
    global lastkill
    global lastkilledobject
    global lastkillassist
    global nextlife

    global event_types
    global object_types

    cursor = dbconn.cursor()
    unparsed = file(unparsedfilename + os.path.basename(filename), 'a')
    errors = file(errorsfilename + os.path.basename(filename), 'a')
    errorcount = 0

    # Start with a guess of the map being played in this file.
    curround.map = guess_map_name(filename)

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
                logging.info("***Loading map '%s'" % curround.map)
                curround.begin = timestamp
                curround.type = 'waiting'
                curround.miniround = 'a'
                curround.point = 1
                curround.overtime = None
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

            if result.miniroundselected:
                curround.overtime = None
                curround.begin = timestamp
                curround.type = 'setup'
                curround.miniround = result.miniroundselected.miniround.strip('"').strip('round_')

                if curround.map == 'plr_pipeline' and curround.miniround == '3':
                    # There is no setup on the third section of pipeline.
                    curround.type = 'normal'

                try:
                    # For some crazy reason, in *some* cases, the
                    # minirounds are named with numbers instead of
                    # letters.  So we have to check if it's a number
                    # and map it to a letter.
                    curround.miniround = chr(ord('a') - 1 + int(curround.miniround))
                except ValueError:
                    pass
                if curround.miniround == 'a':
                    curround.series += 1
                    curround.point = 1


            if result.setupend:
                cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                               (curround.id, curround.map,
                                curround.miniround, 'setup',
                                None, curround.series,
                                curround.begin, timestamp, curround.overtime,
                                None))
                cursor.executemany('insert or ignore into roundlives values (?, ?)',
                                   [(curround.id, life)
                                    for (life, curclass, begin) in curlives.values()])

                curround.id += 1
                curround.overtime = None
                curround.begin = timestamp
                curround.type = 'normal'

            if result.pointcaptured:
                # Record that the round is over and that the capping
                # team won.  Note that in payload race, the capping
                # team may be red.
                curround.end = timestamp
                curround.point = int(result.pointcaptured.cp.strip('"')) + 1
                assert curround.type == 'normal'
                assert curround.point is not None
                cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                               (curround.id, curround.map,
                                curround.miniround, curround.type,
                                curround.point, curround.series,
                                curround.begin, curround.end, curround.overtime,
                                result.pointcaptured.team == 'Blue'))
                cursor.executemany('insert or ignore into roundlives values (?, ?)',
                                   [(curround.id, life)
                                    for (life, curclass, begin) in curlives.values()])


                # Record the capturers
                for p in result.pointcaptured.keys():
                    if p.startswith('player'):
                        player = actor.parseString(result.pointcaptured[p])
                        cursor.execute(
                    # point captured has event type id 9
                    "insert into events values (NULL, 9, ?, ?, ?, NULL, NULL, NULL, ?, NULL, NULL)",
                    (timestamp, player.steamid, curlives[player.steamid][0], curround.id))

                curround.point += 1
                curround.id += 1
                curround.overtime = None
                curround.begin = timestamp
                curround.type = 'normal'

            if result.humiliationbegin:
                # Humiliation begin/miniround won: If blue won, we've
                # already closed the normal round for the last point
                # and recorded the capture.  If red won, we now must
                # close the round.
                if result.humiliationbegin.winner.strip('"') == 'Red':
                    assert curround.point is not None
                    cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                   (curround.id, curround.map,
                                    curround.miniround, 'normal',
                                    curround.point, curround.series,
                                    curround.begin, timestamp, curround.overtime,
                                    False))
                    cursor.executemany('insert or ignore into roundlives values (?, ?)',
                                       [(curround.id, life)
                                        for (life, curclass, begin) in curlives.values()])
                    curround.id += 1

                # And now record the new info for the beginning of the
                # humiliation round.
                curround.begin = timestamp
                curround.bluewin = result.humiliationbegin.winner.strip('"') == 'Blue'
                curround.type = 'humiliation'

            if result.humiliationend:
                if curround.type == 'normal':
                    # An admin restarted the game in the middle of a
                    # round.
                    curround.type = 'aborted'
                cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                               (curround.id, curround.map,
                                curround.miniround, curround.type,
                                None, curround.series,
                                curround.begin, timestamp, None,
                                None))
                cursor.executemany('insert or ignore into roundlives values (?, ?)',
                                   [(curround.id, life)
                                    for (life, curclass, begin) in curlives.values()])
                curround.id += 1
                curround.overtime = None

            # END OF ROUND TRACKING

            # START OF LIFE TRACKING

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
                    weapon = event.weapon.strip('"') if event.weapon else None
                    if event.object:
                        obj = event.object.strip('"').lower()
                        obj = object_types.get(obj)

                    if eventtype in ['killedobject'] and event.assist:
                        eventtype = 'killedobject assist'
                        parent = lastkilledobject

                    if eventtype in ['killedobject', 'killedobject assist']:
                        vicplayer = actor.parseString(event.objectowner).steamid
                    elif eventtype in ['kill assist', 'domination', 'revenge']:
                        vicplayer = actor.parseString(event.vicplayer).steamid
                        if event.assist: # When person gets dom/rev from their assist, not assists w/ a dom/rev
                            parent = lastkillassist
                        else:
                            parent = lastkill
                    elif eventtype in ['captureblocked', 'pointcaptured',
                                       'chargedeployed', 'builtobject']:
                        vicplayer = None
                    else:
                        # Some other event that we don't care about
                        # (e.g. "bm_autobalanceteams switch")
                        continue

                srclife = curlives[srcplayer][0]
                viclife, curclass, begin = curlives.get(vicplayer, (None,None,None))
                if srclife is not None:
                    eventtype = event_types.get(eventtype)
                    cursor.execute("insert into events values (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (eventtype, timestamp,
                                    srcplayer, srclife,
                                    vicplayer, viclife,
                                    weapon, curround.id, parent, obj))
                # Set this event as the most recent kill/kill assist/killedobj
                if result.kill or result.suicide:
                    lastkill = cursor.lastrowid
                if result.event and result.triggered:
                    # eventtype in scope from the similar branch above
                    if eventtype == 'killedobject':
                        lastkilledobject = cursor.lastrowid
                    if eventtype == 'kill assist':
                        lastkillassist = cursor.lastrowid

                # Insert the life that was ended by this kill/suicide.
                if result.kill or result.suicide:
                    end = timestamp
                    cursor.execute("insert or ignore into lives values (?, ?, ?, ?, ?, ?, ?, ?)",
                                   (viclife, vicplayer, curteams[vicplayer], curclass,
                                    begin, end, eventtype, lastkill))
                    cursor.execute("insert or ignore into roundlives values (?, ?)",
                                   (curround.id, viclife))
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
            if result.miniroundselected:
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
                cursor.execute('select count(name) from players where steamid = ?', (steamid,))
                if cursor.fetchone()[0] == 0:
                    cursor.execute('insert into players values (?, ?)',
                                   (steamid, name))
                else:
                    cursor.execute('update players set name = ? where steamid = ?',
                                   (name, steamid))
        except Exception, e:
            print >> errors, e
            print >> errors, line
            print e
            print line
            errorcount += 1
            #raise
    return errorcount

def non_death_end_life(cursor, steamid, team, end, reason):
    global curlives
    global curround
    life, curclass, begin = curlives[steamid]
    if life is not None and begin != end:
        cursor.execute('insert or ignore into lives values (?, ?, ?, ?, ?, ?, ?, ?)',
                       (life, steamid, team, curclass, begin, end, reason, None))
        cursor.execute('insert or ignore into roundlives values (?, ?)',
                       (curround.id, life))

def deb(o):
    print str(type(o)) + ": " + repr(o)

def main(dbfilename, logs):
    dbconn = sqlite3.connect(dbfilename)

    global curround
    global nextlife
    cursor = dbconn.cursor()

    # Support resuming by fetching the max ids already in use.
    cursor.execute('select max(id) from rounds')
    try:
        curround.id = cursor.fetchone()[0] + 1
    except TypeError:
        curround.id = 1
    cursor.execute('select max(id) from lives')
    try:
        nextlife = cursor.fetchone()[0] + 1
    except TypeError:
        nextlife = 1
    cursor.execute('select max(series) from rounds')
    try:
        curround.series = cursor.fetchone()[0] + 1
    except TypeError:
        curround.series = 1
    cursor.close()

    # Fetch the object_types and event_types tables and cache in a dictionary.
    global event_types
    global object_types
    cursor.execute('select event_name, id from event_types')
    event_types = dict(cursor.fetchall())
    cursor.execute('select object_name, id from object_types')
    object_types = dict(cursor.fetchall())

    for filename in logs:
        sys.stdout.write('Processing ' + filename)
        sys.stdout.flush()
        errorcount = processLogFile(filename, dbconn)
        if errorcount != 0:
            print
            print '\t\terrors = %d' % errorcount
        else:
            sys.stdout.write('\r')
    dbconn.commit()
    sys.stdout.write('\nCleaning up')
    # Clean out the meaningless entries in spectators.
    cursor.execute('delete from spectators where begin = end')
    # Clean out lives of 0 seconds.
    cursor.execute('delete from lives where begin = end')
    # Clean up wrong viclife entry on assists, dominations, and
    # revenges.
    cursor.execute("""update events set viclife = (select viclife from events e2 where e2.id = events.parent)
    where type in ('kill assist','domination','revenge')""")
    dbconn.commit()
    dbconn.close()

if __name__ == '__main__':
    if sys.version_info[:2] != (2, 5):
        print >> sys.stderr, "Please run with Python 2.5."
        print >> sys.stderr, "Python 2.6 wants unicode, for which this program is not written."
        sys.exit(2)
    if len(sys.argv[1:]) < 2:
        print >> sys.stderr, 'Usage: python builddb.py filename.db [logfiles]'
        sys.exit(2)
    main(sys.argv[1], sys.argv[2:])
