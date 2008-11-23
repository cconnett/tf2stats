from pyparsing import *

def quoted(s):
    return Literal('"').suppress() + s + Literal('"').suppress()

team = oneOf(['Red','Blue','','Unassigned']).setResultsName('team')
role = oneOf(['scout','soldier','pyro',
              'demoman','heavyweapons','engineer',
              'medic','sniper','spy'])

steamid_re = r'STEAM_\d:\d:\d+'
actor = Regex(r'"(?P<playername>.*)<\d+><(?P<steamid>' + steamid_re +
              r')><(?P<playerteam>Blue|Red||Unassigned)>"')

reason = Regex(r'".*"')

join = actor + 'entered the game'
part = actor + 'disconnected (reason ' + reason + ')'
changeteam = actor + 'joined team "' + team.setResultsName('newteam') + '"'
changerole = actor + 'changed role to "' + role + '"'

capper = (Literal('(player') + Word(nums) + actor + Literal(') (position') +
          Word(nums) + '"' + Word(nums + ' ') + '")')
pointcaptured = (Literal('Team "') + team +
                 Regex(r'" triggered "pointcaptured" .*')) # \(cp ...\) \(cpname "\S*?"\) \(numcappers "\d+"\) ') +
                 #delimitedList(capper, delim=' '))

#filestart = Literal('Log file started') + restOfLine
#ban = Literal('Banid:') + restOfLine
#kill = (actor.setResultsName('killer') + 'killed' +
#        actor.setResultsName('victim') + 'with' + restOfLine)

timestamp = Regex(r'\d{2}/\d{2}/\d{4} - \d{2}:\d{2}:\d{2}:')
logline = (Literal('L ').suppress() +
           timestamp.setResultsName('timestamp') +
           (join.setResultsName('join') |
            part.setResultsName('part') |
            changeteam.setResultsName('changeteam') |
            pointcaptured.setResultsName('pointcaptured')))
