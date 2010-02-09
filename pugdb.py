from datetime import datetime
from pprint import pprint
from pyparsing import ParseException
import logging
import sqlite3
import sys
import os
import mapguesser

from logparser import *

unparsedfilename = '/tmp/unparsed-'
errorsfilename = '/tmp/errors-'
file(unparsedfilename, 'w').close() # Blank the file

class Round(object):
    __slots__ = ['id', 'map', 'type', 'begin']
    def __init__(self, *args):
        for s,v in zip(Round.__slots__, args):
            setattr(self, s, v)
class Fight(object):
    __slots__ = ['id', 'round', 'midowner', 'point', 'begin']
    def __init__(self, *args):
        for s,v in zip(Fight.__slots__, args):
            setattr(self, s, v)

# Fetch the object_types and event_types tables and cache in a dictionary.
event_types = {}
object_types = {}

def processLogFile(filename, dbconn, pugid):
    global event_types
    global object_types
    cursor = dbconn.cursor()
    unparsed = file(unparsedfilename + os.path.basename(filename), 'a')
    errors = file(errorsfilename + os.path.basename(filename), 'a')
    errorcount = 0

    curround = Round(None, None, None, None)
    curfight = Fight(None, None, None, 3, None)
    lastkill = None
    lastkilledobject = None
    lastkillassist = None

    # Support resuming by fetching the max ids already in use.
    cursor.execute('select max(id) from rounds')
    try:
        curround.id = cursor.fetchone()[0] + 1
    except TypeError:
        curround.id = 1

    cursor.execute('select max(id) from fights')
    try:
        curfight.id = cursor.fetchone()[0] + 1
    except TypeError:
        curfight.id = 1

    cursor.execute('select max(id) from lives')
    try:
        nextlife = cursor.fetchone()[0] + 1
    except TypeError:
        nextlife = 1

    # TODO: Come up with the best guesses for all the attributes of
    # the current match.  Map, top 12 players and their classes and
    # teams.

    # Guess the map being played in this file.
    curround.map = mapguesser.guess_map_name(filename)
    if curround.map is None:
        logging.info("Failed to guess map for file '%s'" % filename)
        return errorcount

    curlives = {}
    curteams = {}

    for line in file(filename):
        #print line
        try:
            result = logline.parseString(line)
        except ParseException:
            print >> unparsed, line
            continue
        timestamp = datetime.strptime(result.timestamp, '%m/%d/%Y - %H:%M:%S:')
        try:
            if result.newlogfile:
                curround.begin = timestamp
                curround.type = 'pregame'

            # START OF ROUND/FIGHT TRACKING
            if result.roundstart:
                #curround.id += 1 ###incr
                curround.type = 'normal'
                curround.begin = timestamp

                curfight.begin = timestamp
                curfight.midowner = None
                curfight.point = 3

            if result.setupbegin:
                curfight.begin = timestamp
                curfight.midowner = 'lock'

            if result.setupend:
                # Record the setup fight
                cursor.execute('insert into fights values (?, ?, ?, ?, ?, ?, ?, ?)',
                               (curfight.id, curround.id, curround.map,
                                curfight.midowner, curfight.point, None,
                                curfight.begin, timestamp))
                cursor.executemany('insert or ignore into fightlives values (?, ?)',
                                   [(curfight.id, life)
                                    for (life, curclass, begin) in curlives.values()])

                curfight.id += 1 ###incr
                curfight.begin = timestamp
                curfight.midowner = None

            if result.pointcaptured:
                # Record that current fight is over and that the
                # capping team won.
                assert curfight.point is not None
                cursor.execute('insert into fights values (?, ?, ?, ?, ?, ?, ?, ?)',
                               (curfight.id, curround.id, curround.map,
                                curfight.midowner, curfight.point,
                                result.pointcaptured.team,
                                curfight.begin, timestamp))
                cursor.executemany('insert or ignore into fightlives values (?, ?)',
                                   [(curfight.id, life)
                                    for (life, curclass, begin) in curlives.values()])

                # Record the capturers
                for p in result.pointcaptured.keys():
                    if p.startswith('player'):
                        player = actor.parseString(result.pointcaptured[p])
                        # pointcaptured has event type id 9
                        cursor.execute("insert into events values (NULL, 9, ?, ?, ?, NULL, NULL, NULL, ?, NULL, NULL)",
                                       (timestamp, player.steamid,
                                        curlives[player.steamid][0], curround.id))
                        cursor.execute("insert into cappers values (?, ?)",
                                       (player.steamid, curfight.id))

                # We now want to set the curfight.point to the point
                # that the midowner will be attacking.  The 'cp' field
                # of the pointcaptured event runs from 0 to 4
                # inclusive on 5-point push maps, and refers to the
                # point just captured.  We want the fight's 'point'
                # field to refer to the point that the midowner will
                # now be attacking.
                captured = int(result.pointcaptured.cp.strip('"'))
                # Convert to the more standard 3, 4, 5 terminology,
                # with a midowner reference.
                if captured == 2:
                    # Captured mid, so change midowner, and set point
                    # being attacked to 4.
                    curfight.midowner = result.pointcaptured.team
                    curfight.point = 4
                elif captured in (1,3) and \
                     curfight.midowner == result.pointcaptured.team:
                    # Attacking team captured 4.  Set point being
                    # attacked to 5.
                    curfight.point = 5
                elif captured in (1,3):
                    # Defending team (re)captured 4 (2 from their
                    # perspective).  Set point being attacked (by
                    # midowner) to 4.
                    curfight.point = 4
                elif captured in (0,4):
                    # Attacking team captured last and won the round.
                    # Don't need to set anything here, because there
                    # will be a roundwin event and a roundstart for
                    # next round.
                    pass
                curfight.id += 1 ###incr
                curfight.begin = timestamp

            if result.roundwin or result.roundstalemate:
                assert curround.type == 'normal'
                cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?)',
                               (curround.id, curround.map, curround.type,
                                result.roundwin.winner.strip('"') if result.roundwin else None,
                                curround.begin, timestamp,
                                'capture' if result.roundwin else 'stalemate',
                                pugid))
                cursor.executemany('insert or ignore into fightlives values (?, ?)',
                                   [(curfight.id, life)
                                    for (life, curclass, begin) in curlives.values()])
                if result.roundstalemate:
                    cursor.execute('insert into fights values (?, ?, ?, ?, ?, ?, ?, ?)',
                                   (curfight.id, curround.id, curround.map,
                                    curfight.midowner, curfight.point,
                                    None,
                                    curfight.begin, timestamp))
                    curfight.id += 1 ###incr
                curround.id += 1 ###incr

            # END OF ROUND/FIGHT TRACKING

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
                    #if event.customkill:
                    #    weapon = event.customkill.strip('"')

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
                    #eventtype = event_types.get(eventtype)
                    cursor.execute("insert into events values (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (event_types.get(eventtype), timestamp,
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
                    cursor.execute("insert or ignore into fightlives values (?, ?)",
                                   (curfight.id, viclife))
                    curlives[vicplayer] = (nextlife, curclass, timestamp)
                    nextlife += 1

            if result.changerole:
                steamid = result.changerole.steamid
                newrole = result.changerole.newrole.strip('"')
                if steamid in curlives:
                    non_death_end_life(cursor, steamid, curteams[steamid], timestamp, 'changerole',
                                       curlives, curfight)
                curlives[steamid] = (nextlife, newrole, timestamp)
                nextlife += 1
            if result.changeteam:
                steamid = result.changeteam.steamid
                if result.changeteam.newteam in ['Red', 'Blue']:
                    curteams[steamid] = result.changeteam.newteam
            if result.roundstart or result.gameover:
                for steamid in curlives:
                    non_death_end_life(cursor, steamid, curteams[steamid], timestamp, 'roundend',
                                       curlives, curfight)
                    curlife, curclass, begin = curlives[steamid]
                    curlives[steamid] = (nextlife, curclass, timestamp)
                    nextlife += 1
            if result.leave:
                    quitter = actor.parseString(result.leave.quitter)
                    try:
                        non_death_end_life(cursor, quitter.steamid, quitter.team.lower(), timestamp, 'leaveserver',
                                           curlives, curfight)
                    except KeyError, sqlite3.IntegrityError:
                        pass
                    finally:
                        if quitter.steamid in curlives:
                            del curlives[quitter.steamid]

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
        except KeyError, ke:
            errorcount += 1
            break
        except Exception, e:
            print >> errors, e
            print >> errors, line
            print e
            print line
            errorcount += 1
            raise
    # TODO: compute winner of pug and insert entry into pugs table
    return errorcount

def non_death_end_life(cursor, steamid, team, end, reason, curlives, curfight):
    life, curclass, begin = curlives[steamid]
    if life is not None and begin != end:
        cursor.execute('insert or ignore into lives values (?, ?, ?, ?, ?, ?, ?, ?)',
                       (life, steamid, team, curclass, begin, end, reason, None))
        cursor.execute('insert or ignore into fightlives values (?, ?)',
                       (curfight.id, life))

def deb(o):
    print str(type(o)) + ": " + repr(o)

def main(dbfilename, logs):
    dbconn = sqlite3.connect(dbfilename)
    cursor = dbconn.cursor()

    cursor.execute('select event_name, id from event_types')
    global event_types
    event_types = dict(cursor.fetchall())

    cursor.execute('select object_name, id from object_types')
    global object_types
    object_types = dict(cursor.fetchall())

    cursor.execute('select max(id) from pugs')
    try:
        pugid = cursor.fetchone()[0] + 1
    except TypeError:
        pugid = 1

    lostpugs = 0
    successfulpugs = 0

    for filename in logs:
        sys.stdout.write('Processing ' + filename)
        sys.stdout.flush()
        errorcount = processLogFile(filename, dbconn, pugid)
        if errorcount > 0:
            print
            print '\t\terrors = %d' % errorcount
            dbconn.rollback()
            lostpugs += 1
        else:
            sys.stdout.write('\r')
            dbconn.commit()
            successfulpugs += 1
            pugid += 1
    sys.stdout.write('\nCleaning up\n')
    if lostpugs > 0:
        print 'Lost %d pugs.' % lostpugs
    print 'Successfully processed %d pugs.' % successfulpugs
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
