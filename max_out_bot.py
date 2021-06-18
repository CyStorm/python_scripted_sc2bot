import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer, Human
from sc2.ids.unit_typeid import UnitTypeId as UNITID
from sc2.ids.ability_id import AbilityId as ABILITYID
from sc2.ids.buff_id import BuffId as BUFFID
from sc2.ids.upgrade_id import UpgradeId as UPGRADEID
from base_protoss_bot import BaseProtossBot

class MaxOutBot(BaseProtossBot):
    def __init__(self):
        super().__init__()

    async def on_step(self, iteration):
        self.is_expanding = True
        self.build_worker()
        next_expansion = await self.get_next_expansion()
        self.expand(next_expansion)
        self.watch_mineral_saturation()
        if (self.townhalls.ready.amount >= 2):
            for nexus in self.townhalls.filter(lambda unit: not unit.has_buff(BUFFID.CHRONOBOOSTENERGYCOST)):
                self.do_chronoboost(nexus)

def main():
    # run_game(maps.get("AscensiontoAiurLE"), [Bot(Race.Protoss, MaxOutBot()), Computer(Race.Terran, Difficulty.VeryEasy)], realtime=False)
    # run_game(maps.get("AscensiontoAiurLE"), [Human(Race.Terran), Bot(Race.Protoss, MaxOutBot())], realtime=True)
    run_game(maps.get("AscensiontoAiurLE"), [Bot(Race.Protoss, MaxOutBot()), Human(Race.Terran)], realtime=True)
    # best record 6:57 max out human bot hybrid

if __name__ == "__main__":
    main()
