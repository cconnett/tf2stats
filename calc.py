from datetime import datetime
from logparser import logline
from pprint import pprint
from pyparsing import ParseException
import itertools
import sys
import matplotlib

playernames_by_steamid = {}
def most_common_player_names(playernames_by_steamid):
    ret = {}
    for key in playernames_by_steamid:
        names = playernames_by_steamid[key]
        names.sort()
        groups = [(len(list(group)), val) for (val, group)
                   in itertools.groupby(names)]
        groups.sort()
        ret[key] = groups[-1][1]
    return ret

red = set()
blue = set()

sizes = []
init = None

for line in file(sys.argv[1]):
    try:
        result = logline.parseString(line)
    except ParseException:
        continue
    
    # Collect all steamid--playername associations for canonical naming
    if result.steamid:
        playernames_by_steamid.setdefault(result.steamid,[]).append(result.playername)

    
    timestamp = datetime.strptime(result.timestamp, '%m/%d/%Y - %H:%M:%S:')
    if init is None:
        init = timestamp
    
    if result.changeteam:
        print result.playername, result.steamid, 'joined team', result.changeteam.newteam
        red.discard(result.steamid)
        blue.discard(result.steamid)
        {'Red':red,'Blue':blue}[result.changeteam.newteam].add(result.steamid)
        print '%2d vs. %2d' % (len(red), len(blue))
    if result.part:
        print result.playername, result.steamid, 'left'
        red.discard(result.steamid)
        blue.discard(result.steamid)

    sizes.append( (len(red), len(blue), (timestamp - init).seconds) )

    if result.pointcaptured:
        print result.team
    if result.pointcaptured:
        print result.dump()

#pprint(most_common_player_names(playernames_by_steamid))

#plot([elem[2] for elem in sizes], [elem[0] for elem in sizes], 'r')
#plot([elem[2] for elem in sizes], [elem[1] for elem in sizes], 'b')
