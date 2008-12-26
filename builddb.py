from datetime import datetime
from pprint import pprint
from pyparsing import ParseException
import logging
import sqlite3
import sys

from logparser import logline

# List of memberships in the round currently being processed for which
# the player has not yet left.
active_memberships = []

most_recent_round_start = None
current_roundid = None
current_map = 'pl_goldrush'
current_point = None

def processLogFile(filename, unparsedfilename='/dev/null'):
    unparsed = file(unparsedfilename, 'w')

    roster = {}

    for line in file(filename):
        try:
            result = logline.parseString(line)
        except ParseException:
            print >> unparsed, line

        timestamp = datetime.strptime(result.timestamp, '%m/%d/%Y - %H:%M:%S:')

        # Handle team changes and player parts.
        if result.part or result.changeteam:
            # Remove the player from the roster, and record an entry
            # in the memberships table for their time on that team.
            if result.steamid in roster:
                teamname, join_time = roster[result.steamid]
                part_time = timestamp
                self.liabilities.append((result.steamid, teamname, join_time, part_time))
                del self.roster[result.steamid]

            if result.changeteam:
                logging.debug('%s<%s> joined team %s' %
                              (result.playername, result.steamid, result.changeteam.newteam))
                # Store current timestamp as the join_time in the roster.
                self.roster[result.steamid] = (result.changeteam.newteam, timestamp)

        # Record the map name.
        if result.loadmap:
            self.current_map = result.loadmap.mapname
            self.current_point = 0
            logging.info("***Loading map '%s'" % self.current_map)

        # Create new series and round entries in the database, get
        # their info, and update local state.
        if result.seriesend:
            logging.info('%s won.' % result.winner)
            current_point = 0
            pass

        # On point captured, end the current round, record the capture
        # event as an event, and store the cappers in the captures
        # table.
        if result.pointcaptured:
            logging.info("Blue capped '%s' point %d" % (self.current_map, self.current_point))
            current_point += 1
            logging.debug("Current point now '%s' #%d" % (self.current_map, self.current_point))

        # Record the timestamp of round start.
        if result.roundstart or result.pointcaptured:
            if self.most_recent_round_start is None or \
                   timestamp > self.most_recent_round_start:
                self.most_recent_round_start = timestamp
            else:
                print 'log lines out of order or DST happened', timestamp

if __name__ == '__main__':
    dbconn = sqlite3.connect(sys.argv[1])
    for filename in sys.argv[2:]:
        print 'Processing', filename
        g.processLogFile(filename, dbconn)
    dbconn.close()
