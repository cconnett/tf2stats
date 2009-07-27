import random
import math
import csv
import CascadeGP
import threading
import random
import sys
from numpy import array, zeros, dot

def logistic(x):
    return 1 / (1 + math.exp(-x))

class SkillGP(CascadeGP.CascadeGP):
    def __init__(self, inputs, answers):
        CascadeGP.CascadeGP.__init__(self)
        self.inputs = inputs
        self.answers = answers

    def new_individual(self):
        return array([random.gauss(0, 1.5) for elt in self.inputs[0]])
    def new_offspring(self, parent_a, parent_b):
        crossover = random.randrange(len(parent_a))
        child = list(parent_a)[:crossover] + list(parent_b)[crossover:]
        child = [elt + random.gauss(0, 0.25)
                 if random.random() < 0.02 else elt
                 for elt in child]
        return array(child)

    def evaluate(self, individual):
        numWrong = 0.0
        error = 0.0
        logits = dot(self.inputs, individual)
        for (logit, answer) in zip(logits, self.answers):
            prediction = logistic(logit)
            error += abs(answer - prediction)
            if round(answer - prediction) != 0:
                numWrong += 1.0
        return (numWrong / len(self.inputs),
                error / len(self.inputs),
                sum(map(abs, individual[:-11])),
                )

def main():
    if len(sys.argv) != 2:
        print >> sys.stderr, "Usage: python skillsearch.py output-file"
    r = csv.reader(file('step2.csv'))
    titles = r.next()
    data = [map(float, csValues) for csValues in r]
    inputs = array([datum[:-1] for datum in data])
    answers = array([datum[-1] for datum in data])

    gp = SkillGP(inputs, answers)
    try:
        gp.run()
    except BaseException:
        pass

    print >> file(sys.argv[1],'w'), gp.result

if __name__ == '__main__':
    main()

# Error when predicting 1/2 for all: 0.5
# Benchmark error target: 3608.93 / 13215 = 0.273093
