# from processing import Process, Queue
# NUM_PROCS = 4
# q = Queue()
# procs = [Process(generate_children, args=[q]) for proc in range(4)]
# for proc in procs:
#     proc.start()

import random
import sys
from pprint import pprint

GROUP_SIZE = 500
TOURNAMENT_SIZE = 20
GENERATIONS_PER_CASCADE = 10

class CascadeGP(object):
    def __init__(self,
                 archive_size=GROUP_SIZE,
                 population_size=GROUP_SIZE,
                 tournament_size=TOURNAMENT_SIZE,
                 generations_per_cascade=GENERATIONS_PER_CASCADE):
        self.cascadesWithoutImprovement = 0
        self.archive_size = archive_size
        self.population_size = population_size
        self.tournament_size = tournament_size
        self.generations_per_cascade = generations_per_cascade

        self.result = []
        self.previousFitnesses = []

    # Must override:
    def new_individual(self):
        raise NotImplementedError
    def new_offspring(self, parent_a, parent_b):
        raise NotImplementedError
    def evaluate(self, individual):
        raise NotImplementedError

    # Override to get print-outs of fitness against a test set.
    # System will not optimize against this fitness, it will only
    # print the fitness for human judges.
    def evaluateAgainstTestSet(self, individual):
        raise NotImplementedError

    # May override
    def bored(self):
        return self.cascadesWithoutImprovement >= 2

    # Don't override
    def delete_dominated(self, tournament):
        fits = tournament[:]
        for (fit_a, a) in fits:
            for (fit_b, b) in fits:
                if all(component_a > component_b
                       for (component_a, component_b) in zip(fit_a, fit_b)):
                    tournament.remove((fit_a, a))
                    break

    def run(self):
        archive = [self.new_individual() for i in range(self.archive_size)]
        archive = [(self.evaluate(individual), individual)
                   for individual in archive]

        cascade = 0
        while not self.bored():
            population = [self.new_individual() for i in range(self.population_size)]
            population = [(self.evaluate(individual), individual)
                          for individual in population]
            next_gen = []

            for generation in range(self.generations_per_cascade):
                while len(next_gen) < self.population_size:
                    archive_tournament = random.sample(archive, self.tournament_size)
                    population_tournament = random.sample(population, self.tournament_size)

                    self.delete_dominated(archive_tournament)
                    self.delete_dominated(population_tournament)

                    for pt_winner in population_tournament:
                        at_winner = random.choice(archive_tournament)

                        parents = [pt_winner, at_winner]
                        random.shuffle(parents)
                        first_parent, second_parent = parents
                        child = self.new_offspring(first_parent[1], second_parent[1])
                        next_gen.append((self.evaluate(child), child))

                        if len(next_gen) == self.population_size:
                            break
                    sys.stdout.write('\rGeneration %2d/%2d, next_gen size = %3d/%d' %
                                     (generation+1, self.generations_per_cascade,
                                      len(next_gen), self.population_size))
                    sys.stdout.flush()
                population = next_gen
                next_gen = []
            archive = population

            # Keep a separate collection of the all-time best
            # individuals.  We don't need to maintain genetic
            # diversity here because these don't get recycles back
            # like the archive does.  If a test set evaluation is
            # available, the result collection will be kept based on
            # those evaluations.

            # Re-evaluate against the test set if available.
            reevaluatedArchive = list(sorted(archive))
            try:
                reevaluatedArchive = list(sorted(
                    (self.evaluateAgainstTestSet(individual), individual)
                    for (training_fitness, individual) in archive))
            except NotImplementedError:
                pass

            # Merge the re-evaluated archive into result.  Check if
            # fitnesses changed.
            self.result.extend(reevaluatedArchive)
            self.delete_dominated(self.result)
            fitnesses = [fitness for (fitness, individual) in self.result]
            fitnesses.sort()

            if fitnesses == self.previousFitnesses:
                self.cascadesWithoutImprovement += 1
            else:
                self.cascadesWithoutImprovement = 0

            # Store the previous fitnesses in a separate list.
            self.previousFitnesses = fitnesses

            # Print the number of undominated individuals in result
            # and the fitness of member of result with the best first
            # characteristic.  Increment cascade number.
            sys.stdout.write('\r%d undominated individuals after cascade %d.     \n'
                             % (len(self.result), cascade))
            pprint(fitnesses[0])
            cascade += 1
        print 'Improvement has stopped.'
        return sorted(self.result, key=lambda (fitness, individual): fitness)
