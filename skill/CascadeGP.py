# from processing import Process, Queue
# NUM_PROCS = 4
# q = Queue()
# procs = [Process(generate_children, args=[q]) for proc in range(4)]
# for proc in procs:
#     proc.start()

import random

ARCHIVE_SIZE = 50
POPULATION_SIZE = 50
TOURNAMENT_SIZE = 10
GENERATIONS_PER_CASCADE = 10

class CascadeGP(object):
    def __init__(self):
        self.boredFlag = False

    # To override:
    def new_individual(self):
        raise NotImplemented()
    def new_offspring(self, parent_a, parent_b):
        raise NotImplemented()

    # May override
    def bored(self):
        return self.boredFlag

    # Override one of these.
    def evaluate(self, individual):
        raise NotImplemented()

    def delete_dominated(self, tournament):
        fits = tournament[:]
        for (fit_a, a) in fits:
            for (fit_b, b) in fits:
                if all(component_a < component_b
                       for (component_a, component_b) in zip(fit_a, fit_b)):
                    if (fit_a, a) in tournament:
                        tournament.remove((fit_a, a))

    # Don't override
    def run(self):
        archive = [self.new_individual() for i in range(ARCHIVE_SIZE)]
        archive = [(self.evaluate(individual), individual)
                   for individual in archive]

        while not self.bored():
            print 'Cascade'
            population = [self.new_individual() for i in range(POPULATION_SIZE)]
            population = [(self.evaluate(individual), individual)
                          for individual in population]
            next_gen = []

            for generation in range(10):
                print '\tGeneration %d' % generation
                while len(next_gen) < POPULATION_SIZE:
                    print '\t\tnext_gen size = %3d' % len(next_gen)
                    archive_tournament = random.sample(archive, TOURNAMENT_SIZE)
                    population_tournament = random.sample(population, TOURNAMENT_SIZE)

                    self.delete_dominated(archive_tournament)
                    self.delete_dominated(population_tournament)

                    for pt_winner in population_tournament:
                        at_winner = random.choice(archive_tournament)

                        parents = [pt_winner, at_winner]
                        random.shuffle(parents)
                        first_parent, second_parent = parents
                        child = self.new_offspring(first_parent[1], second_parent[1])
                        next_gen.append((self.evaluate(child), child))

                        if len(next_gen) == POPULATION_SIZE:
                            break
                population = next_gen
                next_gen = []
            archive = population
            self.result = archive
            print list(sorted(archive))[0]
        return archive
