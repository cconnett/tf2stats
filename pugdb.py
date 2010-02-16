from datetime import datetime, timedelta
from pprint import pprint
from pyparsing import ParseException
import logging
import sqlite3
import sys
import os
import mapguesser
import itertools
import respawnwaves
import attributedrow

from logparser import *

unparsedfilename = '/tmp/unparsed-'
errorsfilename = '/tmp/errors-'
file(unparsedfilename, 'w').close() # Blank the file

class Round(object):
    __slots__ = ['id', 'map', 'type', 'begin', 'wavecalculator']
    def __init__(self):
        for slot in Round.__slots__:
            setattr(self, slot, None)
class Fight(object):
    __slots__ = ['id', 'round', 'midowner', 'point', 'begin']
    def __init__(self, *args):
        for slot in Fight.__slots__:
            setattr(self, slot, None)

class BadPugException(Exception): pass
class NotAPugException(Exception): pass

# Fetch the object_types and event_types tables and cache in a dictionary.
event_types = {}
object_types = {}

def processLogFile(filename, cursor, pugid):
    global event_types
    global object_types
    unparsed = file(unparsedfilename + os.path.basename(filename), 'a')
    errors = file(errorsfilename + os.path.basename(filename), 'a')
    errorcount = 0

    curround = Round()
    curfight = Fight()
    curfight.point = 3
    lastkill = None
    lastkilledobject = None
    lastkillassist = None
    unspawnedDeaths = set()

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
        nextlife = itertools.count(cursor.fetchone()[0] + 1)
    except TypeError:
        nextlife = itertools.count(1)

    # Guess the map being played in this file.
    curround.map = mapguesser.guess_map_name(filename)
    if curround.map is None:
        logging.info("Failed to guess map for file '%s'" % filename)
        raise NotAPugException()

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
            updateRespawnTimes(cursor, curlives, curround,
                               timestamp, unspawnedDeaths)

            if result.newlogfile:
                curround.begin = timestamp
                curround.type = 'pregame'
                curfight.begin = timestamp

            # START OF ROUND/FIGHT TRACKING
            if result.roundstart or result.gameover:
                # End the lives of anyone not killed in humiliation.
                for steamid in curlives:
                    end_life(cursor, steamid, curteams[steamid], timestamp,
                             'roundend', curlives, curround)
                    curlife, curclass, begin, spawn = curlives[steamid]
                    curlives[steamid] = (nextlife.next(), curclass, timestamp, timestamp)
                # Clear unspawnedDeaths for the new round
                unspawnedDeaths.clear()

                # End the pregame fight/round or the humiliation fight
                # of the previous round.
                if curround.type == 'pregame':
                    end_fight(cursor, curlives, curfight, curround,
                              timestamp, None,
                              humiliation=False)
                    end_round(cursor, curlives, curround,
                              timestamp, None, 'gamestart', pugid)
                elif curround.type == 'normal':
                    # The humiliation fight gets attached to the
                    # previous round.
                    end_fight(cursor, curlives, curfight, curround,
                              timestamp, None,
                              humiliation=True)
                    # No separate round just for the humiliation fight.

                if result.gameover:
                    # Finish all processing of this pug log file.
                    return

                curround.type = 'normal'
                curround.wavecalculator = None
                curfight.midowner = None
                curfight.point = 3

                curround.id += 1
                curround.begin = timestamp


            if result.setupbegin:
                curfight.begin = timestamp
                curfight.midowner = 'lock'

            if result.setupend:
                # Record the setup fight
                end_fight(cursor, curlives, curfight, curround,
                          timestamp, None, humiliation=False)

            if result.pointcaptured:
                assert curfight.point is not None

                # Record the capturers
                for p in result.pointcaptured.keys():
                    if p.startswith('player'):
                        player = actor.parseString(result.pointcaptured[p])
                        # pointcaptured has event type id 9
                        cursor.execute("insert into events values (NULL, 9, ?, ?, ?, NULL, NULL, NULL, ?, ?, NULL, NULL)",
                                       (timestamp, player.steamid,
                                        curlives[player.steamid][0],
                                        curfight.id, curround.id))
                        cursor.execute("insert into cappers values (?, ?)",
                                       (player.steamid, curfight.id))

                # Record that current fight is over and that the
                # capping team won.
                end_fight(cursor, curlives, curfight, curround, timestamp,
                          result.pointcaptured.team, humiliation=False)

                # Notify the respawn wave calculator of the capture.
                if curround.wavecalculator is not None:
                    cursor.execute('''
                    select midowner, point, winner, end as "end [timestamp]"
                    from fights where rowid = ?''',
                                   (cursor.lastrowid,))
                    fight = cursor.fetchone()
                    curround.wavecalculator.notifyOfCapture(fight)

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
                curfight.id += 1
                curfight.begin = timestamp

            if result.roundwin or result.roundstalemate:
                assert curround.type == 'normal'
                if result.roundstalemate:
                    end_fight(cursor, curlives, curfight, curround, timestamp, None,
                              humiliation=False)
                end_round(cursor, curlives, curround, timestamp,
                          result.roundwin.winner.strip('"') if result.roundwin else None,
                          'capture' if result.roundwin else 'stalemate', pugid)
                unspawnedDeaths.clear()

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
                viclife, curclass, begin, spawn = curlives.get(vicplayer, (None,None,None,None))
                if srclife is not None:
                    #eventtype = event_types.get(eventtype)
                    cursor.execute("insert into events values (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (event_types.get(eventtype), timestamp,
                                    srcplayer, srclife,
                                    vicplayer, viclife,
                                    weapon, curfight.id, curround.id,
                                    parent, obj))
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
                    if curround.type == 'pregame' and begin is not None:
                        spawn = begin + timedelta(seconds=5)
                    cursor.execute("insert into lives values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (viclife, vicplayer, curteams[vicplayer], curclass,
                                    begin, end, eventtype, lastkill, curround.id, spawn))
                    curlives[vicplayer] = (nextlife.next(), curclass, timestamp, None)
                    if curround.wavecalculator is None:
                        curround.wavecalculator = respawnwaves.WaveCalculator(timestamp)
                    cursor.execute('''select
                    e.time, l.team, l.player from lives l
                    join events e on l.deathevent = e.id
                    where l.rowid = ?''', (cursor.lastrowid,))
                    death = cursor.fetchone()
                    unspawnedDeaths.add(death)

            if result.changerole:
                steamid = result.changerole.steamid
                newrole = result.changerole.newrole.strip('"')
                if steamid in curlives:
                    end_life(cursor, steamid, curteams[steamid], timestamp,
                             'changerole', curlives, curround)
                    pass
                if steamid in curlives and curlives[steamid][3] is None:
                    spawnTime = None
                else:
                    spawnTime = timestamp
                # Put them into curlives even if they're not in it
                # now, for a player's first class selection.
                curlives[steamid] = (nextlife.next(), newrole, timestamp, spawnTime)

            if result.changeteam:
                steamid = result.changeteam.steamid
                if steamid in curteams:
                    del curteams[steamid]
                if result.changeteam.newteam in ['Red', 'Blue', 'Spectator']:
                    curteams[steamid] = result.changeteam.newteam
            if result.leave:
                quitter = actor.parseString(result.leave.quitter)
                try:
                    end_life(cursor, quitter.steamid, quitter.team, timestamp,
                             'leaveserver', curlives, curround)
                except KeyError, sqlite3.IntegrityError:
                    pass
                finally:
                    if quitter.steamid in curlives:
                        del curlives[quitter.steamid]
                    unspawnedDeaths = set(death for death in unspawnedDeaths
                                          if death.player != quitter.steamid)

                if quitter.steamid in curteams:
                    del curteams[quitter.steamid]

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
            raise BadPugException(ke)
        except Exception, e:
            print >> errors, e
            print >> errors, line
            print e
            print line
            raise

def end_life(cursor, steamid, team, end, reason, curlives, curround):
    life, curclass, begin, spawn = curlives[steamid]
    if life is not None and begin != end:
        cursor.execute('insert into lives values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (life, steamid, team.title(), curclass, begin, end,
                        reason, None, curround.id, spawn))

def end_fight(cursor, curlives, curfight, curround, timestamp, cappingteam, humiliation):
    assert curfight.point is not None
    cursor.execute('insert into fights values (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (curfight.id, curround.id, curround.map,
                    curfight.midowner, curfight.point,
                    cappingteam,
                    curfight.begin, timestamp, humiliation))
    curfight.id += 1
    curfight.begin = timestamp

def end_round(cursor, curlives, curround, timestamp, cappingteam,
              endreason, pugid):
    cursor.execute('insert into rounds values (?, ?, ?, ?, ?, ?, ?, ?)',
                   (curround.id, curround.map, curround.type,
                    cappingteam, curround.begin, timestamp,
                    endreason, pugid))

def updateRespawnTimes(cursor, curlives, curround, timestamp, unspawnedDeaths):
    wc = curround.wavecalculator
    spawns = set()
    #print set((timestamp - death.time).seconds for death in unspawnedDeaths)
    for death in unspawnedDeaths:
        spawnTime = wc.timeOfWave(death.team, wc.respawnWave(death))
        if spawnTime <= timestamp:
            curlife, curclass, begin, _ = curlives[death.player]
            curlives[death.player] = (curlife, curclass, begin, spawnTime)
            spawns.add(death)
    unspawnedDeaths -= spawns

def deb(o):
    print str(type(o)) + ": " + repr(o)

def main(dbfilename, logs):
    dbconn = sqlite3.connect(dbfilename,
                             detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
    cursor = dbconn.cursor()

    cursor.execute('select event_name, id from event_types')
    global event_types
    event_types = dict(cursor.fetchall())

    cursor.execute('select object_name, id from object_types')
    global object_types
    object_types = dict(cursor.fetchall())

    cursor.execute('select max(pug) from rounds')
    try:
        pugid = cursor.fetchone()[0] + 1
    except TypeError:
        pugid = 1

    cursor.close()
    dbconn.row_factory = attributedrow.AttributedRow
    cursor = dbconn.cursor()

    badpugs = 0
    successfulpugs = 0

    for filename in logs:
        sys.stdout.write('Processing ' + os.path.basename(filename))
        sys.stdout.flush()
        try:
            processLogFile(filename, cursor, pugid)
        except BadPugException, e:
            print
            print '\t Bad pug!'
            dbconn.rollback()
            badpugs += 1
        except NotAPugException, e:
            pass
        else:
            dbconn.commit()
            successfulpugs += 1
            pugid += 1
        finally:
            sys.stdout.write('\r' + (' ' * 70) + '\r')
    sys.stdout.write('\nCleaning up... ')
    # Clean out lives 0 seconds or negative time.
    cursor.execute('delete from lives where begin >= end')
    # Clean up wrong viclife entry on assists, dominations, and
    # revenges.
    cursor.execute("""update events set viclife = (select viclife from events e2 where e2.id = events.parent)
    where type in ('kill assist','domination','revenge')""")
    cursor.execute("analyze")
    dbconn.commit()
    cursor.close()
    dbconn.close()
    sys.stdout.write('done.\n')
    if badpugs > 0:
        print '%d bad pugs.' % badpugs
    print 'Successfully processed %d pugs.' % successfulpugs

if __name__ == '__main__':
    if sys.version_info[:2] != (2, 5):
        print >> sys.stderr, "Please run with Python 2.5."
        print >> sys.stderr, "Python 2.6 wants unicode, for which this program is not written."
        sys.exit(2)
    if len(sys.argv[1:]) < 2:
        print >> sys.stderr, 'Usage: python builddb.py filename.db [logfiles]'
        sys.exit(2)
    main(sys.argv[1], sys.argv[2:])
