from pyparsing import *

def quoted(s):
    return Literal('"').suppress() + s + Literal('"').suppress()

team = oneOf(['Red','Blue','','Unassigned','Console','Spectator']).setResultsName('team')

steamid_re = r'STEAM_\d:\d:\d+'
actor = Regex(r'"(?P<playername>.*)<\d+><(?P<steamid>' + steamid_re +
              r')><(?P<playerteam>Blue|Red||Unassigned|Console|Spectator)>"')

reason = Regex(r'".*"')

join = actor + 'entered the game'
part = actor + 'disconnected (reason ' + reason + ')'
changeteam = actor + 'joined team "' + team.setResultsName('newteam') + '"'

capper = (Literal('(player') + Word(nums) + actor + Literal(') (position') +
          Word(nums) + '"' + Word(nums + ' ') + '")')
pointcaptured = (Literal('Team "') + team +
                 Regex(r'" triggered "pointcaptured" .*')) # \(cp ...\) \(cpname "\S*?"\) \(numcappers "\d+"\) ') +
                 #delimitedList(capper, delim=' '))

roundstart = Literal('World triggered "Round_Setup_End"')
roundend = Literal('World triggered "Round_Win" (winner "') + team.setResultsName('winner') + '")'
loadmap = Literal('Loading map "') + oneOf(['pl_badwater','pl_goldrush']).setResultsName('mapname') + '"'

timestamp = Regex(r'\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}:')
logline = (Literal('L ').suppress() +
           timestamp.setResultsName('timestamp') +
           (join.setResultsName('join') |
            part.setResultsName('part') |
            changeteam.setResultsName('changeteam') |
            pointcaptured.setResultsName('pointcaptured') |
            roundstart.setResultsName('roundstart') |
            roundend.setResultsName('roundend') |
            loadmap.setResultsName('loadmap')
            ))
