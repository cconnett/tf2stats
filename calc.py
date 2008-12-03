from __future__ import division
from datetime import datetime
from math import sqrt
from pprint import pprint
from pyparsing import ParseException
import cPickle
import itertools
import logging
import numpy
import sys

from logparser import logline
from sign_flip import sign_flip_svd

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

floatpair = (0.0,0.0)

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
        self.scores = {}

        self.playernames = {}
        self.players = None

    def processLogFile(self, filename):
        for line in file(filename):
            try:
                result = logline.parseString(line)
            except ParseException:
                continue

            # Collect all steamid--playername associations for
            # canonical naming.
            if result.steamid:
                self.playernames.setdefault(result.steamid,[]).append(result.playername)

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
                if self.most_recent_round_start is None or \
                       timestamp > self.most_recent_round_start:
                    self.most_recent_round_start = timestamp
                else:
                    print 'log lines out of order'

    def update_scores(self, time_of_event, (winner, loser)):
        time_taken = time_of_event - self.most_recent_round_start
        if not time_taken:
            return

        def generate_attempts(target_teamname=None):
            """Generate tuples representing the responsibility of
            every player involved in the event leading to this update
            of scores."""
            for (steamid, (teamname, join_time)) in self.roster.items():
                if target_teamname is None or target_teamname == teamname:
                    yield (steamid, teamname, join_time, time_of_event)
            for (steamid, teamname, join_time, part_time) in self.liabilities:
                if target_teamname is None or target_teamname == teamname:
                    yield (steamid, teamname, join_time, part_time)

        # If there are enough players to count this for scoring.
        if len(list(None for (steamid, (teamname, join_time)) in self.roster.items()
                    if teamname in ['Red','Blue'])) >= self.min_players:
            # For every edge in complete bipartite graph of the teams
            for (steamid_blue, teamname, join_time, end_time) in generate_attempts('Blue'):
                time_on_team = (max(end_time, self.most_recent_round_start) -
                                max(join_time, self.most_recent_round_start))
                time_on_team = max(time_on_team, time_taken)
                attempt_fraction_blue = (time_on_team.seconds / time_taken.seconds)
                for (steamid_red, teamname, join_time, end_time) in generate_attempts('Red'):
                    time_on_team = (max(end_time, self.most_recent_round_start) -
                                    max(join_time, self.most_recent_round_start))
                    time_on_team = max(time_on_team, time_taken)
                    attempt_fraction_red = (time_on_team.seconds / time_taken.seconds)

                    combined_attempt_fraction = attempt_fraction_blue * attempt_fraction_red

                    (successes_blue, attempts_blue) = \
                                     self.scores.get((steamid_blue, steamid_red), floatpair)
                    (successes_red, attempts_red) = \
                                    self.scores.get((steamid_red, steamid_blue), floatpair)

                    if winner == 'Blue':
                        self.scores[(steamid_blue, steamid_red)] = \
                                                   (successes_blue + combined_attempt_fraction,
                                                    attempts_blue + combined_attempt_fraction)
                        self.scores[(steamid_red, steamid_blue)] = \
                                                   (successes_red + 0,
                                                    attempts_red + combined_attempt_fraction)
                    elif winner == 'Red':
                        self.scores[(steamid_blue, steamid_red)] = \
                                                   (successes_blue + 0,
                                                    attempts_blue + combined_attempt_fraction)
                        self.scores[(steamid_red, steamid_blue)] = \
                                                   (successes_red + combined_attempt_fraction,
                                                    attempts_red + combined_attempt_fraction)
        else:
            logging.debug('Fewer than %d players, not scoring.' % self.min_players)
        self.liabilities = []

    def most_common_player_names(self):
        """Return a dictionary containing the most common playername used
        by each steamid, given the list of playernames used by each
        steamid."""
        ret = {}
        for key in self.playernames:
            names = self.playernames[key]
            names.sort()
            groups = [(len(list(group)), val) for (val, group)
                       in itertools.groupby(names)]
            groups.sort()
            ret[key] = groups[-1][1]
        self.players = ret


def harmonic_mean(seq):
    return 1/sum(1/x for x in seq)

map_numpoints = {'pl_goldrush':7, 'pl_badwater':4}

if __name__ == '__main__':
    try:
        g = cPickle.load(file(sys.argv[1]))
        print 'Loaded', sys.argv[1]
    except (cPickle.UnpicklingError, ValueError, EOFError, IndexError), e:
        g = GameTracker()
        for filename in sys.argv[1:]:
            print 'Processing', filename
            g.processLogFile(filename)
        cPickle.dump(g, file('default.pyp','w'), 2)

    g.most_common_player_names()
    numplayers = len(g.players)

    matrix = numpy.zeros((numplayers, numplayers))
    for (i, (steamid_blue, common_name)) in enumerate(g.players.items()):
        for (j, (steamid_red, common_name)) in enumerate(g.players.items()):
            successes, attempts = g.scores.get((steamid_blue, steamid_red), floatpair)
            try:
                matrix[i,j] = (successes / attempts)
            except ZeroDivisionError:
                matrix[i,j] = 0.0

    u,s,v = sign_flip_svd(matrix)
    offense_skills = u[:,0]
    defense_skills = v[0,:]

    skills = []
    for ((steamid, common_name), offense_skill, defense_skill) in \
            sorted(zip(g.players.items(), offense_skills, defense_skills)):
        skills.append((harmonic_mean([offense_skill, defense_skill]), common_name))

    min_skill = min(skill for (skill, name) in skills)
    max_skill = max(skill - min_skill for (skill, name) in skills)

    skills = [((skill-min_skill) / max_skill, name) for (skill, name) in skills]
    for (skill, common_name) in sorted(skills, reverse=True):
        print '%7.2f %s' % (skill*1000, common_name)
