from __future__ import division
from collections import defaultdict
from datetime import datetime
from math import sqrt
from pprint import pprint
from pyparsing import ParseException
import itertools
import logging
import numpy
import sys

from logparser import logline
from sign_flip import sign_flip_svd

playernames = {}
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

        # Record of all point-player scores.  Scores are stored as
        # 2-tuples of floats, successes and attempts.  This score dict
        # will include the score for all points across all supported
        # maps, even though SVD may be run separately for separate
        # maps.  Keys are tuples --- (mapname, point_number, steamid,
        # teamname ('Red' or 'Blue')).  Maps to floating point scores.
        self.scores = defaultdict(lambda: (0.0,0.0))

    def processLogFile(self, filename):
        for line in file(filename):
            try:
                result = logline.parseString(line)
            except ParseException:
                continue

            # Collect all steamid--playername associations for
            # canonical naming.
            if result.steamid:
                playernames.setdefault(result.steamid,[]).append(result.playername)

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
                self.update_scores(timestamp, ('Blue', 'Red'))
                self.current_point += 1
                logging.debug("Current point now '%s' #%d" % (self.current_map, self.current_point))

            # On red win, credit everyone on red, and punish everyone
            # on blue.
            if result.roundend:
                if result.winner == 'Red':
                    self.update_scores(timestamp, ('Red', 'Blue'))
                else:
                    # Blue's scores were already updated when they
                    # triggered pointcaptured
                    pass
                self.current_point = 0
                logging.info('%s won.' % result.winner)

            # Record the timestamp of round start.
            if result.roundstart or result.pointcaptured:
                self.most_recent_round_start = timestamp

    def update_scores(self, time_of_event, (winner, loser)):
        time_taken = time_of_event - self.most_recent_round_start

        def generate_attempts():
            """Generate tuples representing the responsibility of
            every player involved in the event leading to this update
            of scores."""
            for (steamid, (teamname, join_time)) in self.roster.items():
                yield (steamid, teamname, join_time, time_of_event)
            for (steamid, teamname, join_time, part_time) in self.liabilities:
                yield (steamid, teamname, join_time, part_time)

        if len(list(None for (steamid, (teamname, join_time)) in self.roster.items()
                    if teamname in ['Red','Blue'])) >= self.min_players:
            # If there are enough players to count this for scoring.
            for (steamid, teamname, join_time, end_time) in generate_attempts():
                time_on_team = (max(end_time, self.most_recent_round_start) -
                                max(join_time, self.most_recent_round_start))
                assert time_on_team.seconds <= time_taken.seconds

                attempt_fraction = (time_on_team.seconds / time_taken.seconds)

                key = (self.current_map, self.current_point, steamid, teamname)
                (successes, attempts) = self.scores[key]
                if teamname == winner:
                    self.scores[key] = (successes + attempt_fraction,
                                        attempts + attempt_fraction)
                elif teamname == loser:
                    self.scores[key] = (successes + 0,
                                        attempts + attempt_fraction)

                logging.debug('   %s on %s for %d out of %d seconds, %s %f',
                              steamid, teamname,
                              time_on_team.seconds, time_taken.seconds,
                              {winner:'rewarded', loser:'penalized'}.get(teamname, 'ignoring'),
                              attempt_fraction)
                
        else:
            logging.debug('Fewer than %d players, not scoring.' % self.min_players)
        self.liabilities = []

map_numpoints = {'pl_goldrush':7, 'pl_badwater':4}

if __name__ == '__main__':
    g = GameTracker()
    for filename in sys.argv[1:]:
        print 'Processing', filename
        g.processLogFile(filename)

    players = most_common_player_names(playernames)
    numplayers = len(players)

    for (mapname, numpoints) in map_numpoints.items():
        matrix = numpy.zeros((numpoints, numplayers))
        for point in range(numpoints):
            i = point
            for (j, (steamid, common_name)) in enumerate(players.items()):
                for teamname in ['Red', 'Blue']:
                    successes, attempts = g.scores[(mapname, point, steamid, teamname)]
                    if teamname == 'Blue':
                        try:
                            matrix[i,j] = (successes / attempts)
                        except ZeroDivisionError:
                            matrix[i,j] = 0.5

        u,s,v = sign_flip_svd(matrix)
        point_difficulties = u[:,0]
        player_skills = v[0,:]

        point_difficulties
        point_difficulties /= max(point_difficulties)
        print point_difficulties
        #print player_skills
