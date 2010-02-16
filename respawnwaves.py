import datetime

BIG_WAVE_TIME = 8
SMALL_WAVE_TIME = 5

class WaveCalculator(object):
    def __init__(self, firstDeathTime):
        self.references = {}
        self.waveTime = {}

        self.references['Blue'] = self.references['Red'] = (firstDeathTime, 0)
        self.waveTime['Blue'] = self.waveTime['Red'] = BIG_WAVE_TIME

    def respawnWave(self, death):
        """Return the respawn wave in which the player killed by the
        given death event will respawn."""

        victimTeam = death.team
        referenceTime, referenceWave = self.references[victimTeam]
        timeSinceReference = (death.time - referenceTime)
        secondsSinceReference = timeSinceReference.seconds + (86400 * timeSinceReference.days)

        wavesSinceReference = (secondsSinceReference - 1) // self.waveTime[victimTeam]
        respawnWave = referenceWave + wavesSinceReference + 3

        return respawnWave

    def timeOfWave(self, team, wave):
        """Return the time at which the given respawn wave will occur."""

        referenceTime, referenceWave = self.references[team]
        respawnTime = (referenceTime +
                       (wave - referenceWave) *
                       datetime.timedelta(seconds=self.waveTime[team]))
        return respawnTime

    def nextWaveOfTime(self, team, time):
        """Return the wave number of the wave that occurs at or
        soonest after the given time."""

        referenceTime, referenceWave = self.references[team]
        nextWave = referenceWave + \
                   (time - referenceTime).seconds // self.waveTime[team] + \
                   ((time - referenceTime).seconds % self.waveTime[team] != 0)
        return nextWave

    def notifyOfCapture(self, fight):
        """Call this when a capture occurs with the fight that the
        capture ends, so that this object can change the respawn wave
        intervals of the teams."""

        if fight.midowner is None:
            return

        nextWave = self.nextWaveOfTime(fight.midowner, fight.end)
        #print nextWave, self.timeOfWave(fight.midowner, nextWave)
        self.references[fight.midowner] = (
            self.timeOfWave(fight.midowner, nextWave), nextWave
            )

        if fight.point == 4 and fight.midowner == fight.winner:
            # Midowner capped 4 and their wave time will decrease.
            self.waveTime[fight.midowner] = SMALL_WAVE_TIME
        elif fight.point == 5 and fight.midowner != fight.winner:
            # Midowner lost 4 and their wave time will increase.
            self.waveTime[fight.midowner]= BIG_WAVE_TIME
        else:
            # No other captures change wave times.
            pass
