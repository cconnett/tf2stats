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
        assert len(inputs) == len(answers)
        CascadeGP.CascadeGP.__init__(self)
        self.inputs = inputs
        self.answers = answers
        self.testIndices = set(
            random.sample(range(len(self.inputs)),
                          int(round(float(len(self.inputs))/8))))

    def new_individual(self):
        return array([random.gauss(0, 1.5) for elt in self.inputs[0]])
    def new_offspring(self, parent_a, parent_b):
        crossover = random.randrange(len(parent_a))
        child = list(parent_a)[:crossover] + list(parent_b)[crossover:]
        child = [elt + random.gauss(0, 0.25)
                 if random.random() < 0.02 else elt
                 for elt in child]
        return array(child)

    def evaluate(self, individual, againstTestSet=False):
        if againstTestSet:
            numCases = len(self.testIndices)
        else:
            numCases = len(self.inputs) - len(self.testIndices)
        numWrong = 0
        sqError = 0.0
        logits = dot(self.inputs, individual)
        for (i, (logit, answer)) in enumerate(zip(logits, self.answers)):
            if againstTestSet ^ (i in self.testIndices):
                continue
            prediction = logistic(logit)
            sqError += (answer - prediction) ** 2
            if round(answer - prediction) != 0:
                numWrong += 1
        return (float(numWrong) / numCases, # pct of wrong instances
                math.sqrt(sqError / numCases), # RMSE
                sum(map(abs, individual[:-11])) +
                sum(map(abs, individual[-11:])) / 4, # model size
                # The division by 4 says allow the point's coefficient
                # to be roughly equivalent to four players worth of
                # skill coefficients.
                )
    def evaluateAgainstTestSet(self, individual):
        return self.evaluate(individual, againstTestSet = True)

def main():
    if len(sys.argv) != 2:
        print >> sys.stderr, "Usage: python skillsearch.py output-file"
    r = csv.reader(file('step2.csv'))
    titles = r.next()
    data = [map(float, csValues) for csValues in r]
    #data = [datum for datum in data if any(datum[-12:-8])] # badwater rounds only
    #data = [datum for datum in data if any([datum[-8],datum[-6],datum[-4],datum[-3]])] # goldrush easy rounds only
    #data = [datum for datum in data if any([datum[-7],datum[-5],datum[-2]])] # goldrush hard rounds only
    inputs = array([datum[:-1] for datum in data])
    answers = array([datum[-1] for datum in data])

    gp = SkillGP(inputs, answers)
    try:
        gp.run()
    except KeyboardInterrupt:
        sys.stdout.write('\n')

    print >> file(sys.argv[1],'w'), gp.result

if __name__ == '__main__':
    main()

# Error when predicting 1/2 for all: 0.5
# Benchmark error target: 3608.93 / 13215 = 0.273093
