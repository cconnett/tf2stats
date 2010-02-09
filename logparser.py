from pyparsing import *
import operator

team = oneOf(['Red','Blue','','Unassigned','Console','Spectator']).setResultsName('team')

player = Regex(r'"(?P<name>.{,32}?)<\d+><STEAM_(?P<steamid>\d:\d:\d+)>'
               r'<(?P<team>Blue|Red||Unassigned|Console|Spectator)>"')
actor = player

reason = Regex(r'".*"')

parameters = dictOf(Literal('(').suppress() + Regex(r'\w+'),
                    (dblQuotedString + Literal(')').suppress()))

kill = actor.setResultsName('killer') + 'killed' + actor.setResultsName('victim') + \
       'with' + dblQuotedString.setResultsName('weapon') + parameters
suicide = actor.setResultsName('suicider') + 'committed suicide with' + \
          dblQuotedString.setResultsName('weapon') + parameters
triggered_event = actor.setResultsName('srcplayer') + 'triggered' + \
                  dblQuotedString.setResultsName('eventname') + \
                  Optional(Literal('against') + actor.setResultsName('vicplayer')) + \
                  parameters
event = kill.setResultsName('kill') | \
        triggered_event.setResultsName('triggered') | \
        suicide.setResultsName('suicide')

line_kinds = {
    'event': event,

    'changerole': actor + 'changed role to' + dblQuotedString.setResultsName('newrole'),
    'changeteam': actor + 'joined team "' + team.setResultsName('newteam') + '"',

    'pointcaptured': Literal('Team "') + team + '" triggered "pointcaptured"' + parameters,

    'miniroundselected': Literal('World triggered "Mini_Round_Selected" (round') + dblQuotedString.setResultsName('miniround') + ')',
    'setupbegin': Literal('World triggered "Round_Setup_Begin"'),
    'setupend': Literal('World triggered "Round_Setup_End"'),
    'gameover': Literal('World triggered "Game_Over"'),
    'overtime': Literal('World triggered "Round_Overtime"'),
    'roundstart': Literal('World triggered "Round_Start"'),
    'roundstalemate': Literal('World triggered "Round_Stalemate"'),
    'roundwin': Literal('World triggered "Round_Win"') + parameters,
    'roundlength': Literal('World triggered "Round_Length"') + parameters,
    'miniroundwin': Literal('World triggered "Mini_Round_Win"') + parameters,

    'enter': actor.setResultsName('newplayer') + 'entered the game',
    'leave': actor.setResultsName('quitter') + 'disconnected (reason ' + reason + ')',
    'changename': actor + 'changed name to' + dblQuotedString.setResultsName('newplayer'),

    'loadmap': Literal('Loading map "') + Regex(r'\w+').setResultsName('mapname') + '"',
    'newlogfile': Literal('Log file started') + parameters,
}
timestamp = Regex(r'\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}:')
logline = (Literal('L ').suppress() +
           timestamp.setResultsName('timestamp') +
           MatchFirst([element.setResultsName(name)
                       for (name, element) in line_kinds.items()]))
sam = '"[EVGA*Bandit] ^Sh4rpSh0ot3r^<2423><STEAM_0:1:19550821><Blue>" triggered "killedobject" (object "OBJ_DISPENSER") (weapon "tf_projectile_pipe_remote") (objectowner "[EVGA*Bandit] MasterMegaManX<2420><STEAM_0:1:6438533><Red>") (attacker_position "-2456 1949 -127")'
