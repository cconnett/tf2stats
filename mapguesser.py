import re
from pprint import pprint
import itertools

map_names = {
    'cp_granary':     r'Granary_cap_((blue|red)_)?cp[123]',
    'cp_badlands':    r'\#Badlands_cap_((blue|red)_)?cp[123]',
    'cp_yukon_final': r'(Blue|Red) (Bridge|Base)|Center Control Point',
    'cp_follower':    r'(BLU|RED) (Front Assault|Base)|Central Heights',

    'cp_well':        r'\#Well_cap_((blue|red)_)?(rocket|two|center).*?position1 ".*? -[234]\d\d"',
    'cp_freight':     r'\#Well_cap_((blue|red)_)?(rocket|two|center).*?position1 ".*? -[678]\d\d"',
    'cp_fastlane':    r'\#Well_cap_((blue|red)_)?(rocket|two|center).*?position1 ".*? -?1?\d\d"',

    'ctf':            r'"flagevent" \(event "captured"\)',
}
# come up with some data structure for the regexes.  probably a
# dictionary mapping map names to regexes, then we can count total
# matches of each regex, and guess the map name with the most matches.

def count_cap_name_occurances(string):
    return lambda map_name: len(re.findall(map_names[map_name], string))

def guess_map_name(logfile):
    """Count the number of appearances of each map's cap point regex
    in logfile, then return the name of the map with the most
    occurances.  Returns None if there were no occurances of any
    regex, and '???' if more than one map is tied."""
    data = file(logfile).read()
    counts = [(count_cap_name_occurances(data)(map_name), map_name)
              for map_name in map_names]
    counts.sort(reverse=True)
    #pprint(counts)
    top_group = itertools.groupby(counts, lambda x:x[0]).next()
    #print top_group
    if top_group[0] == 0:
        return None

    top_maps = list(top_group[1])
    if len(top_maps) > 1:
        return '???'
    else:
        return top_maps[0][1]

if __name__ == '__main__':
    import sys
    for arg in sys.argv[1:]:
        map = guess_map_name(arg)
        if map is not None:
            print map
