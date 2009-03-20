import random
import math
import csv
import search
import sys
import utils
import traceback
from numpy import array, zeros, dot

def logistic(x):
    return 1 / (1 + math.exp(-x))

def successor(state):
    i = random.randrange(len(state))
    ret = state[:]
    ret[i] += random.gauss(0, 0.05)
    return ret

def successor2(state):
    return [elt + (random.gauss(0, 0.10) if random.random() < 0.3 else 0)
            for elt in state]

def geom_mean(a, b):
    return math.sqrt(a*b)

def value(data):
    def closure(state):
        numWrong = 0.0
        for datum in data:
            logit = dot(state, datum[:-1])
            prediction = logistic(logit)
            if round(datum[-1] - prediction) != 0:
                numWrong += 1

        return numWrong / len(data)
    return closure

def simulated_annealing(initial, successor, value,
                        schedule=search.exp_schedule()):
    current = initial
    val_cur = value(current)
    try:
        for t in xrange(sys.maxint):
            T = schedule(t)
            print '%5d %0.4f %0.6f' % (t, T, val_cur)
            if T == 0:
                return current
            next = successor(current)
            val_next = value(next)
            delta_e = val_next - val_cur
            if delta_e < 0 or utils.probability(math.exp(-delta_e/T)):
                current = next
                val_cur = val_next
    except BaseException, e:
        traceback.print_exc()
        return current

def main():
    r = csv.reader(file('../step2.csv'))
    titles = r.next()
    data = [array(map(float, csValues)) for csValues in r]

    valueFunc = value(data)
    final = simulated_annealing(
        zeros((len(titles) - 1,)),
        successor2, valueFunc,
        schedule=search.exp_schedule(k=0.1, lam=0.0015))

    print valueFunc(final)
    print final

if __name__ == '__main__':
    main()

# Error when predicting 1/2 for all: 0.5
# Benchmark error target: 3608.93 / 13215 = 0.273093
