from __future__ import division
from collections import defaultdict
from datetime import datetime
from logparser import logline
from pprint import pprint
from pyparsing import ParseException
import itertools
import logging
import matplotlib
import sys

playernames_by_steamid = {}
def most_common_player_names(playernames_by_steamid):
    """return a dictionary containing the most common playername used
    by each steamid, given the list of playernames used by each
    steamid."""
    ret = {}
    for key in playernames_by_steamid:
        names = playernames_by_steamid[key]
        names.sort()
        groups = [(len(list(group)), val) for (val, group)
                   in itertools.groupby(names)]
        groups.sort()
        ret[key] = groups[-1][1]
    return ret

# We will track when a player joined a team, and when the most recent
# point started.  If a player leaves a team early, we'll add them to a
# special list of pending liabilities so that they are
# credited/punished for their share of a win/loss after they've left
# the team.  Pending liabilities must include when they joined the
# team as well as when they leave.  When a point ends, we can see for
# each player on the team at point end, when they joined the team.  If
# it was before the most recent point start, their credit starts at
# that point start.  If they're still on the team at point end, their
# credit extends to the point end.  We then process pending
# liabilities to come up with total liability for everyone who played
# any part of the point.

class GameTracker(object):
    def __init__(self, min_players=10):
        # The minimum number of players on both teams to record
        # scores.
        self.min_players = min_players
        # Mappings of when players joined the team they're on.
        self.roster = {}
        # List of pending liabilities.
        self.liabilities = []

        self.most_recent_round_start = None
        self.current_map = 'pl_goldrush'
        self.current_point = 0

        # Record of all point-player scores.  This will include the score
        # for all points across all supported maps, even though SVD may be
        # run separately for separate maps.  Keys are tuples --- (mapname,
        # point_number, steamid, teamname ('Red' or 'Blue')).  Maps to
        # floating point scores.
        self.scores = defaultdict(float)

    def processLogFile(self, filename):
        for line in file(filename):
            try:
                result = logline.parseString(line)
            except ParseException:
                continue

            # Collect all steamid--playername associations for
            # canonical naming.
            if result.steamid:
                playernames_by_steamid.setdefault(result.steamid,[]).append(result.playername)

            timestamp = datetime.strptime(result.timestamp, '%m/%d/%Y - %H:%M:%S:')

            # Handle team changes and player parts.
            if result.part or result.changeteam:
                # Remove the player from the roster, and record a pending
                # liability for their time on that team.
                if result.steamid in self.roster:
                    teamname, join_time = self.roster[result.steamid]
                    self.liabilities.append((result.steamid, teamname, join_time, timestamp))
                    del self.roster[result.steamid]

                if result.part:
                    pass
                    logging.debug('%s<%s> left' % (result.playername, result.steamid))
                if result.changeteam:
                    logging.debug('%s<%s> joined team %s' %
                                  (result.playername, result.steamid, result.changeteam.newteam))
                    # Store join time as the value in the roster.
                    self.roster[result.steamid] = (result.changeteam.newteam, timestamp)

            # Record the map name.
            if result.loadmap:
                self.current_map = result.loadmap.mapname
                self.current_point = 0
                logging.info("***Loading '%s'" % self.current_map)

            # On point captured, credit everyone on blue, and punish
            # everyone on red.
            if result.pointcaptured:
                logging.info("Blue capped '%s' point %d" % (self.current_map, self.current_point))
                self.update_scores(timestamp, {'Red':-1, 'Blue':1})
                self.current_point += 1
                logging.debug("Current point now '%s' #%d" % (self.current_map, self.current_point))

            # On red win, credit everyone on red, and punish everyone
            # on blue.
            if result.roundend:
                if result.winner == 'Red':
                    self.update_scores(timestamp, {'Red':1, 'Blue':-1})
                else:
                    # Blue's scores were already updated when they
                    # triggered pointcaptured
                    pass
                self.current_point = 0
                logging.info('%s won.' % result.winner)

            # Record the timestamp of round start.
            if result.roundstart or result.pointcaptured:
                self.most_recent_round_start = timestamp

    def update_scores(self, time_of_event, team_sign):
        time_taken = time_of_event - self.most_recent_round_start

        def generate_awards():
            for (steamid, (teamname, join_time)) in self.roster.items():
                yield (steamid, teamname, join_time, time_of_event)
            for (steamid, teamname, join_time, part_time) in self.liabilities:
                yield (steamid, teamname, join_time, part_time)

        if len(list(None for (steamid, (teamname, join_time)) in self.roster.items()
                    if teamname in ['Red','Blue'])) >= self.min_players:
            for (steamid, teamname, join_time, end_time) in generate_awards():
                time_on_team = (max(end_time, self.most_recent_round_start) -
                                max(join_time, self.most_recent_round_start))
                assert time_on_team.seconds <= time_taken.seconds

                award = team_sign.get(teamname, 0) * (time_on_team.seconds / time_taken.seconds)
                self.scores[(self.current_map, self.current_point, steamid, teamname)] += award
                logging.debug('   %s on %s for %d out of %d seconds, adding %f' % \
                              (steamid, teamname, time_on_team.seconds, time_taken.seconds, award))
        else:
            logging.debug('Fewer than %d players, not scoring.' % self.min_players)
        self.liabilities = []

if __name__ == '__main__':
    g = GameTracker()
    for filename in sys.argv[1:]:
        g.processLogFile(filename)
