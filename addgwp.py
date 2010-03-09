import csv
import sys
import itertools
import math
from collections import defaultdict

def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))

playerstats = csv.reader(file(sys.argv[1]))
out = csv.writer(file(sys.argv[2], 'w'))
headers = playerstats.next()
out.writerow(headers)

fields = dict(zip(headers, itertools.count()))

coeffs = defaultdict(float)
coeffs['kpm'] = 0.482795
coeffs['dpm'] = -0.509169

for line in playerstats:
    logit = 0
    for field, index in fields.items():
        try:
            logit += coeffs[field] * float(line[index])
        except ValueError:
            pass
    #print line[fields['kpm']], line[fields['dpm']], logit
    line[fields['gwp']] = sigmoid(logit)
    out.writerow(line)
