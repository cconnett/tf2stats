from pyparsing import *
import operator

team = oneOf(['Red','Blue','','Unassigned','Console','Spectator']).setResultsName('team')

steamid_re = r'STEAM_\d:\d:\d+'
player = Regex(r'"(?P<playername>.*)<\d+><(?P<steamid>' + steamid_re +
               r')><(?P<playerteam>Blue|Red||Unassigned|Console|Spectator)>"')
actor = player | (Literal('Team') + team)

reason = Regex(r'".*"')

parameter = Literal('(').suppress() + \
            Regex('\w+').setResultsName('parameter') + \
            dblQuotedString.setResultsName('value') + \
            Literal(')').suppress()
parameters = Group(OneOrMore(parameter)).setResultsName('parameters')

kill = actor.setResultsName('killer') + 'killed' + actor.setResultsName('victim') + \
       'with' + dblQuotedString.setResultsName('weapon') + parameters
triggered_event = actor + 'triggered' + dblQuotedString.setResultsName('eventname') + \
                  parameters
event = kill | triggered_event

line_kinds = {
    'join': actor + 'entered the game',
    'part': actor + 'disconnected (reason ' + reason + ')',
    'changeteam': actor + 'joined team "' + team.setResultsName('newteam') + '"',
    'gamestart': Literal('World triggered "Round_Setup_End"'),
    'seriesend': Literal('World triggered "Round_Win" (winner "') + team.setResultsName('winner') + '")',
    'loadmap': Literal('Loading map "') + Regex(r'\w+').setResultsName('mapname') + '"',
    'event': event
}
timestamp = Regex(r'\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}:')
logline = (Literal('L ').suppress() +
           timestamp.setResultsName('timestamp') +
           reduce(operator.ior,
                  (element.setResultsName(name)
                   for (name, element) in line_kinds.items())))
