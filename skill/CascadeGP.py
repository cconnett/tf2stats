# from processing import Process, Queue
# NUM_PROCS = 4
# q = Queue()
# procs = [Process(generate_children, args=[q]) for proc in range(4)]
# for proc in procs:
#     proc.start()

import random
import sys

GROUP_SIZE = 500
TOURNAMENT_SIZE = 20
GENERATIONS_PER_CASCADE = 10

class CascadeGP(object):
    def __init__(self,
                 archive_size=GROUP_SIZE,
                 population_size=GROUP_SIZE,
                 tournament_size=TOURNAMENT_SIZE,
                 generations_per_cascade=GENERATIONS_PER_CASCADE):
        self.boredFlag = False
        self.archive_size = archive_size
        self.population_size = population_size
        self.tournament_size = tournament_size
        self.generations_per_cascade = generations_per_cascade

        self.result = []

    # Must override:
    def new_individual(self):
        raise NotImplemented()
    def new_offspring(self, parent_a, parent_b):
        raise NotImplemented()
    def evaluate(self, individual):
        raise NotImplemented()

    # May override
    def bored(self):
        return self.boredFlag

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
            self.result.extend(archive)
            self.delete_dominated(self.result)
            sys.stdout.write('\r%d undominated individuals.                      \n'
                             % len(self.result))
            bestOne = list(sorted(self.result))[0]
            print bestOne[0]
        return self.result
