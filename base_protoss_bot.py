import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer, Human
from sc2.ids.unit_typeid import UnitTypeId as UNITID
from sc2.ids.ability_id import AbilityId as ABILITYID
from sc2.ids.buff_id import BuffId as BUFFID
from sc2.ids.upgrade_id import UpgradeId as UPGRADEID

from loguru import logger

from build_orders import one_gate_expand

class BaseProtossBot(sc2.BotAI):
    def __init__(self):
        self.build_order_step = 0
        self.build_order_stage = 0
        self.build_order = None

        self.nexuses = None
        self.main_army = None
        self.production = None
        self.warpgates = None

        self.owned_minearls = None
        self.owned_empty_geysers = None

        self.is_expanding = True
        self.probes_on_gas = 0

        self.has_warpgate = False
        # can do self.gas_buildings built in

    def initial_setup(self):
        main_base_nexus = self.structures(UNITID.NEXUS).first
        self.owned_minearls = self.mineral_field.closer_than(distance=8, position=main_base_nexus.position)
        self.owned_empty_geysers = self.vespene_geyser.closer_than(distance=8, position=main_base_nexus.position)

    async def on_start(self):
        '''built in function
        '''
        self.initial_setup()
        self.set_unit_groups()
        self.pick_build_order()

    def pick_build_order(self):
        self.build_order = one_gate_expand

    async def on_step(self, iteration: int):
        '''built in function
        '''
        # self.build_order_complete = True    # skip initial build order, remove for normal operations
        next_gateway = await self.find_placement(UNITID.GATEWAY, near=self.nexuses.first.position)
        next_pylon = await self.find_placement(UNITID.COMMANDCENTER, near=self.nexuses.random.position)  # use CC for reasons
        next_expansion = await self.get_next_expansion()
        self.watch_gas_saturation()
        if(self.build_order_stage == 2):
            print("stage 2")
            self.set_unit_groups()
            # can abosrb building placement into 1 place
            self.build_pylon(location=next_pylon)
            # self.expand(location=next_expansion)
            # self.do_chronoboost(self.nexuses.first)
            # self.build_any_structure(UNITID.GATEWAY, location=next_gateway)
            # self.build_worker()
            # self.build_worker()
            # self.build_pylon(next_pylon)
            # self.build_gas()
            # self.assign_to_gas(3)
        elif (self.build_order_stage == 0):
            print("stage 0")
            self.set_unit_groups()
            self.do_build_order(natural_location=next_expansion, be=next_pylon, building_location=next_gateway)
        elif (self.build_order_stage == 1):
            self.set_unit_groups()
            print("stage 1")
            self.build_pylon(location=next_pylon)
            if (self.workers.amount < 45):
                self.build_worker()
            if (not self.structures(UNITID.TWILIGHTCOUNCIL)):
                self.build_any_structure(UNITID.TWILIGHTCOUNCIL, next_gateway)
            self.train_unit(UNITID.STALKER)

    def set_unit_groups(self):
        self.nexuses = self.structures(UNITID.NEXUS)
        self.gateways = self.structures(UNITID.GATEWAY)

    def do_build_order(self, **kwargs):
        '''Do a pre defined build order, should prob re write
        Should only contain code to execute (any) build order, but currently hard coded for 1
        current does up to 22 pylon in 1 gate expand
        '''
        max_steps = len(self.build_order)
        if (self.build_order_step == max_steps):
            self.build_order_stage = 1
            print("build order done")
            return

        # TODO this info should be part of the build order object? not here
        if (self.build_order_step == 8):
            self.probes_on_gas = 1
        elif (self.build_order_step == 9):
            self.probes_on_gas = 2
        elif (self.build_order_step == 10):
            self.probes_on_gas = 3
        elif (self.build_order_step == 16):
            self.probes_on_gas = 6

        current_step = self.build_order[self.build_order_step]
        if (current_step[0] == "b" or current_step[0] == "v"):
            # structures
            # TODO better build order implimentation, mapping no all hard coded here
            structures = {
                "bg": UNITID.GATEWAY,
                "by": UNITID.CYBERNETICSCORE,
                "be": UNITID.PYLON,
                "ba": UNITID.ASSIMILATOR,
                2: self.main_base_ramp.protoss_wall_pylon,
                5: self.main_base_ramp.protoss_wall_buildings[1],
                13: self.main_base_ramp.protoss_wall_buildings[0],
            }
            location = structures.get(self.build_order_step, None)
            if (not location):
                location = kwargs.get(current_step, kwargs["building_location"])
            result = self.build_any_structure(structures[current_step], location)
        elif (current_step[0] == "a"):
            # ability cast
            if (current_step[1] == "c"):
                result = self.do_chronoboost(self.nexuses.first)
        elif (current_step == "w"):
            # probe
            result = self.build_worker()
        elif (current_step == "ex"):
            # expand
            result = self.expand(kwargs["natural_location"])
        else:
            # TODO impliment other build order steps
            result = False

        if (result):
            self.build_order_step += 1

    def build_worker(self):
        success = False
        nexus = self.townhalls.idle
        if (nexus and self.can_afford(UNITID.PROBE)):
            nexus.random.train(UNITID.PROBE, queue=True)
            success = True
        return success

    def build_pylon(self, location):
        success = False
        if (self.supply_used + 8 > self.supply_cap and not self.already_pending(UNITID.PYLON)):
            if (self.can_afford(UNITID.PYLON)):
                if (location):
                    worker = self.select_build_worker(location)
                    worker.build(UNITID.PYLON, location)
                    worker.gather(self.owned_minearls.closest_to(worker.position), queue=True)
                    success = True
        return success

    def build_gas(self):
        success = False
        if (self.can_afford(UNITID.ASSIMILATOR) and self.owned_empty_geysers):
            gyser = self.owned_empty_geysers.pop(0)
            # need to update the owned_empty_geysers if one was destroyed
            build_probe = self.select_build_worker(gyser)
            build_probe.build(UNITID.ASSIMILATOR, gyser)
            build_probe.gather(self.owned_minearls.closest_to(build_probe.position), queue=True)
            success = True
        return success

    def build_any_structure(self, building_id: UNITID, location):
        if (building_id == UNITID.PYLON):
            return self.build_pylon(location)
        elif (building_id == UNITID.ASSIMILATOR):
            return self.build_gas()
        success = False
        if (self.can_afford(building_id)):
            if (location):
                worker = self.select_build_worker(location)
                worker.build(building_id, location)
                worker.gather(self.owned_minearls.closest_to(worker.position), queue=True)
                success = True
        return success

    def assign_to_gas(self, amount, worker=None):
        for _ in range(0, amount):
            for assimilator in self.gas_buildings.ready:
                if (assimilator.assigned_harvesters < assimilator.ideal_harvesters):
                    eligible_workers = self.units(UNITID.PROBE).filter(lambda worker: worker.is_carrying_minerals)
                    worker = eligible_workers.closest_to(assimilator.position)
                    worker.gather(assimilator, queue=True)
                    break
        if (worker):
            for assimilator in self.gas_buildings.ready:
                if (assimilator.assigned_harvesters < assimilator.ideal_harvesters):
                    worker.gather(assimilator, queue=True)
                    break

    def remove_from_gas(self, amount, worker=None):
        if (amount):
            workers = self.units(UNITID.PROBE).filter(lambda worker: worker.is_carrying_vespene).random_group_of(amount)
            for probe in workers:
                probe.gather(self.owned_minearls.closest_to(probe.position), queue=True)
        if (worker):
            worker.gather(self.owned_minearls.closest_to(worker.position), queue=True)

    def watch_gas_saturation(self):
        '''Assign probes to gas as the internal variable dictates
        '''
        count = 0
        for assimilator in self.gas_buildings:
            count += assimilator.assigned_harvesters
        if (count == self.probes_on_gas):
            return
        elif (count < self.probes_on_gas and not (self.probes_on_gas < self.gas_buildings.ready.amount)):
            self.assign_to_gas(self.probes_on_gas - count)
        elif(count > self.probes_on_gas):
            self.remove_from_gas(count - self.probes_on_gas)

    def watch_mineral_saturation(self):
        '''Optimize mineral saturaton, from oversaturation in bases, or non-optimal per patch saturation
        '''
        for nexus in self.nexuses.ready:
            pass

    def do_chronoboost(self, target_structure: sc2.unit.Unit):
        '''Uses chronoboost on target structure
        '''
        success = False
        if (not target_structure.has_buff(BUFFID.CHRONOBOOSTENERGYCOST)):
            source = None
            for nexus in self.nexuses:
                if (nexus.energy >= 50):
                    nexus(ABILITYID.EFFECT_CHRONOBOOSTENERGYCOST, target_structure)
                    success = True
                    break
        return success

    def expand(self, location):
        success = False
        if (self.is_expanding and self.can_afford(UNITID.NEXUS)):
            if (location):
                worker = self.select_build_worker(location)
                worker.build(UNITID.NEXUS, location)
                worker.gather(self.owned_minearls.closest_to(worker.position), queue=True)
                self.is_expanding = False
                success = True
        return success

    def train_unit(self, unit_id: UNITID, amount=1):

        success = False
        if (self.tech_requirement_progress(unit_id) < 1):
            return success
        gateway = self.gateways.idle
        if (gateway and self.can_afford(unit_id) and self.can_feed(unit_id)):
            gateway.random.train(unit_id)
            success = True
        return success

    async def on_unit_created(self, unit: sc2.unit.Unit):
        '''built in function
        '''
        if (unit.type_id == UNITID.PROBE):
            unit.gather(self.owned_minearls.closest_to(unit.position))

    async def on_building_construction_complete(self, unit: sc2.unit.Unit):
        '''built in function
        '''
        if (unit.type_id == UNITID.NEXUS):
            new_minearls = self.mineral_field.closer_than(distance=8, position=unit.position)
            self.owned_minearls += new_minearls
            new_gases = self.vespene_geyser.closer_than(distance=8, position=unit.position)
            self.owned_empty_geysers += new_gases
        elif (unit.type_id == UNITID.CYBERNETICSCORE):
            success = False
            while (not success):
                success = self.research(UPGRADEID.WARPGATERESEARCH)
        elif (unit.type_id == UNITID.TWILIGHTCOUNCIL):
            success = False
            while (not success):
                success = self.research(UPGRADEID.BLINKTECH)
        print("done building {}".format(unit))

    async def on_unit_destroyed(self, unit_tag: int):
        ''' built in function
        ueses tags instead of unit objects, because destroyed, duh
        need to remove it from any groups containing it
        '''
        # if (unit_tag in self.nexuses.tags):
        print("unit {} destroyed".format(unit_tag))

def main():
    run_game(maps.get("AscensiontoAiurLE"), [Bot(Race.Protoss, BaseProtossBot()), Computer(Race.Terran, Difficulty.Easy)], realtime=True)
    # run_game(maps.get("AscensiontoAiurLE"), [Human(Race.Terran), Bot(Race.Protoss, BaseProtossBot())], realtime=True)

if __name__ == "__main__":
    main()
