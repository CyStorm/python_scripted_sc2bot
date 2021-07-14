import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer, Human
from sc2.ids.unit_typeid import UnitTypeId as UNITID
from sc2.ids.ability_id import AbilityId as ABILITYID
from sc2.ids.buff_id import BuffId as BUFFID
from sc2.ids.upgrade_id import UpgradeId as UPGRADEID

from loguru import logger

from economy_micro import EconomyMicro
from build_orders import one_gate_expand

class BaseProtossBot(sc2.BotAI, EconomyMicro):
    def __init__(self):
        self.build_order_step = 0
        self.build_order_stage = 0
        self.build_order = None

        self.main_army = None
        self.production = None
        self.warpgates = None

        self.owned_minerals = None          # minerals in all owned bases
        self.owned_empty_geysers = None         # empty gases in all owned bases

        self.is_expanding = True

        self.has_warpgate = False
        self.has_blink = False

        self.stalkers = None
        # can do self.gas_buildings built in

    def initial_setup(self):
        '''Sets control groups and set up internal variables
        '''
        main_base_nexus = self.structures(UNITID.NEXUS).first
        self.newest_base = main_base_nexus
        self.owned_minerals = self.mineral_field.closer_than(distance=8, position=main_base_nexus.position)
        self.owned_empty_geysers = self.vespene_geyser.closer_than(distance=8, position=main_base_nexus.position)

    async def on_start(self):
        '''Built in function, called before the first step
        '''
        self.initial_setup()
        self.set_unit_groups()
        self.pick_build_order()

    def pick_build_order(self):
        self.build_order = one_gate_expand

    async def on_step(self, iteration: int):
        '''Built in function, the main thing called for each iteration of the game
        '''
        # self.build_order_complete = True    # skip initial build order, remove for normal operations
        next_gateway = await self.find_placement(UNITID.GATEWAY, near=self.townhalls.first.position, placement_step=6)
        next_pylon = await self.find_placement(UNITID.COMMANDCENTER, near=self.townhalls.random.position, placement_step=4)  # use CC for reasons
        next_expansion = await self.get_next_expansion()
        warpin_location = await self.find_warpin_location()

        self.set_unit_groups()
        if(self.build_order_stage == 2):
            self.is_expanding = self.townhalls.amount < 3
            # can abosrb building placement into 1 place
            await self.build_pylon(location=next_pylon)
            self.expand(location=next_expansion)
            self.train_unit(UNITID.STALKER, location=warpin_location)
            self.build_gas()
            self.do_micro()
            await self.do_macro()
            if (self.workers.amount < 66):
                self.build_worker()
            if (iteration % 25 == 0):
                self.watch_gas_saturation()
                self.watch_mineral_saturation()

            if (self.stalkers.amount > 25):
                for stalker in self.stalkers:
                    stalker.attack(self.enemy_start_locations[0])

        elif (self.build_order_stage == 0):
            await self.do_build_order(natural_location=next_expansion, be=next_pylon, building_location=next_gateway)
        elif (self.build_order_stage == 1):
            # if (iteration % 25 == 0):
            self.watch_mineral_saturation()
            self.watch_gas_saturation()
            self.get_critical_tech()
            if ((not self.has_blink) and self.already_pending_upgrade(UPGRADEID.BLINKTECH) > 0):
                self.do_chronoboost(self.structures(UNITID.TWILIGHTCOUNCIL).first)
            await self.build_pylon(location=next_pylon)
            if (self.workers.amount < 45):
                self.build_worker()
            if (not self.structures(UNITID.TWILIGHTCOUNCIL)):
                await self.build_any_structure(UNITID.TWILIGHTCOUNCIL, next_gateway)
            self.train_unit(UNITID.STALKER, location=warpin_location)
            if (self.structures(UNITID.GATEWAY).amount + self.warp_gate_count < 6):
                await self.build_any_structure(UNITID.GATEWAY, next_gateway)
            else:
                self.build_order_stage = 2

    def set_unit_groups(self):
        '''Set control groups
        '''
        self.gateways = self.structures(UNITID.GATEWAY)
        self.warpgates = self.structures(UNITID.WARPGATE)
        self.stalkers = self.units(UNITID.STALKER)

    async def do_build_order(self, **kwargs):
        '''Do a pre defined build order, should prob re write
        Should only contain code to execute (any) build order
        '''
        max_steps = len(self.build_order)
        if (self.build_order_step == max_steps):
            self.build_order_stage = 1
            print("build order done")
            return

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
            result = await self.build_any_structure(structures[current_step], location)
        elif (current_step[0] == "a"):
            # ability cast
            if (current_step[1] == "c"):
                result = self.do_chronoboost(self.townhalls.first)
            elif (current_step[1] == "r"):
                if (current_step[2] == "a"):
                    self.townhalls.first(ABILITYID.RALLY_NEXUS, self.gas_buildings.first)
                elif (current_step[2] == "m"):
                    self.townhalls.first(ABILITYID.RALLY_NEXUS, self.owned_minerals.closest_to(self.townhalls.first))
                result = True
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
        '''Make a probe from a nexus, afford check and idle check, with queue
        '''
        success = False
        nexus = self.townhalls.idle
        if (nexus and self.can_afford(UNITID.PROBE)):
            nexus.random.train(UNITID.PROBE, queue=True)
            success = True
        return success

    async def build_pylon(self, location):
        '''Builds pylon, checks if we are withing 8 supply of cap and not already building one
        '''
        success = False
        if (self.supply_used + 8 > self.supply_cap and not self.already_pending(UNITID.PYLON)):
            if (self.can_afford(UNITID.PYLON)):
                if (location):
                    worker = self.select_build_worker(location)
                    try:
                        worker.build(UNITID.PYLON, location)
                        worker.gather(self.owned_minerals.closest_to(worker.position), queue=True)
                        success = True
                    except AttributeError:
                        success = False
        return success

    def build_gas(self):
        '''Build gas on a geyser close to a owned base
        '''
        success = False
        if (self.can_afford(UNITID.ASSIMILATOR) and self.owned_empty_geysers):
            gyser = self.owned_empty_geysers.pop(0)
            # need to update the owned_empty_geysers if one was destroyed
            build_probe = self.select_build_worker(gyser)
            try:
                build_probe.build(UNITID.ASSIMILATOR, gyser)
                build_probe.gather(self.owned_minerals.closest_to(build_probe.position), queue=True)
                success = True
            except AttributeError:
                success = False
        return success

    async def build_any_structure(self, building_id: UNITID, location_override=None):
        '''Build any structure, the pylon and gas will call its own methods
        all structures are 3x3
        '''
        # hooks to other methods, will consolidate later
        if (building_id == UNITID.PYLON):
            return await self.build_pylon(location_override)
        elif (building_id == UNITID.ASSIMILATOR):
            return self.build_gas()
        elif (building_id == UNITID.NEXUS):
            return self.expand()

        success = False
        if (location_override):
            location = location_override
        else:
            location = await self.find_placement(UNITID.GATEWAY, near=self.townhalls.first.position, placement_step=6)
        if (location):
            worker = self.select_build_worker(location)
            if (worker and self.can_afford(building_id)):
                try:
                    worker.build(building_id, location)
                    worker.gather(self.owned_minerals.closest_to(worker.position), queue=True)
                    success = True
                except AttributeError:
                    success = False
        return success

    def do_chronoboost(self, target_structure: sc2.unit.Unit):
        '''Uses chronoboost on target structure
        '''
        success = False
        if (not target_structure.has_buff(BUFFID.CHRONOBOOSTENERGYCOST)):
            source = None
            for nexus in self.townhalls:
                if (nexus.energy >= 50):
                    nexus(ABILITYID.EFFECT_CHRONOBOOSTENERGYCOST, target_structure)
                    success = True
                    break
        return success

    def expand(self, location):
        '''Expands in the next location, need to pass in a location
        '''
        success = False
        if (self.is_expanding and self.can_afford(UNITID.NEXUS)):
            if (location):
                worker = self.select_build_worker(location)
                try:
                    worker.build(UNITID.NEXUS, location)
                    worker.gather(self.owned_minerals.closest_to(worker.position), queue=True)
                    self.is_expanding = False
                    success = True
                except AttributeError:
                    success = False
        return success

    async def find_warpin_location(self):
        '''Finds a 1x1 space near the closest pylon to enemy to warp in units
        '''
        if (not self.has_warpgate):
            return None
        pylon = self.structures(UNITID.PYLON).closest_to(self.enemy_start_locations[0])
        location = await self.find_placement(UNITID.SENSORTOWER, near=pylon.position, max_distance=7)
        return location

    def train_unit(self, unit_id: UNITID, amount=1, location=None):
        ''' Currently only does gateway and warpgate
        '''
        success = False
        if (self.tech_requirement_progress(unit_id) < 1):
            return success
        if (self.has_warpgate):
            gates = self.warpgates.idle
            for warpgate in gates:
                if (self.can_afford(unit_id) and self.can_feed(unit_id)):
                    warpgate.warp_in(unit_id, location)
                    success = True
        else:
            gateway = self.gateways.idle
            if (gateway and self.can_afford(unit_id) and self.can_feed(unit_id)):
                gateway.random.train(unit_id)
                success = True
            return success

    def get_critical_tech(self):
        '''For blink build only gets blink and warpgate
        '''
        techs = [UPGRADEID.WARPGATERESEARCH, UPGRADEID.BLINKTECH]
        for tech in techs:
            self.research(tech)

    def do_micro(self):
        '''Micros the army, clean up some code in on_step to put in here
        '''
        pass

    async def do_macro(self):
        '''Expands and does buildings, clean up scattered code
        '''
        if ((self.structures(UNITID.GATEWAY).amount + self.warp_gate_count) < (self.townhalls.amount * 4)):
            next_gateway = await self.find_placement(UNITID.GATEWAY, near=self.townhalls.first.position, placement_step=6)
            await self.build_any_structure(UNITID.GATEWAY, next_gateway)

    async def on_unit_created(self, unit: sc2.unit.Unit):
        '''Built in function, called on each unit creation, structures not counted
        '''
        if (unit.type_id == UNITID.STALKER):
            gather_location = self.newest_base.position.towards(self.enemy_start_locations[0], 10)
            unit.smart(gather_location)

    async def on_building_construction_complete(self, unit: sc2.unit.Unit):
        '''Built in functino, called on each structure finish construction
        '''
        if (unit.type_id == UNITID.NEXUS):
            new_minearls = self.mineral_field.closer_than(distance=8, position=unit.position)
            self.owned_minerals += new_minearls
            new_gases = self.vespene_geyser.closer_than(distance=8, position=unit.position)
            self.owned_empty_geysers += new_gases
            self.newest_base = unit
            unit(ABILITYID.RALLY_NEXUS, self.owned_minerals.closest_to(unit.position))
        print("done building {}".format(unit))

    async def on_unit_destroyed(self, unit_tag: int):
        ''' built in function
        ueses tags instead of unit objects, because destroyed, duh
        need to remove it from any groups containing it
        '''
        # if (unit_tag in self.townhalls.tags):
        print("unit {} destroyed".format(unit_tag))

    async def on_upgrade_complete(self, upgrade: UPGRADEID):
        """built in function
        """
        if (upgrade == UPGRADEID.WARPGATERESEARCH):
            self.has_warpgate = True
        elif (upgrade == UPGRADEID.BLINKTECH):
            self.has_blink = True

    async def on_unit_took_damage(self, unit: sc2.unit.Unit, amount_damage_taken: float):
        """built in function
        Currently blinks back low hp stalkers
        """
        # blink logic TODO add kiting logic
        if (unit.type_id == UNITID.STALKER):
            if (unit.shield_percentage < 0.15):
                enemy_unit = self.enemy_units.closest_to(unit).position
                if (enemy_unit):
                    target_postion = unit.position.towards(enemy_unit, -5)
                else:
                    target_postion = unit.position.towards(self.start_location, 5)
                unit(ABILITYID.EFFECT_BLINK, target_postion)

def main():
    # For bot vs built in computer
    run_game(maps.get("AscensiontoAiurLE"), [Bot(Race.Protoss, BaseProtossBot()), Computer(Race.Terran, Difficulty.VeryHard)], realtime=False)
    # For bot vs human
    # run_game(maps.get("AscensiontoAiurLE"), [Human(Race.Terran), Bot(Race.Protoss, BaseProtossBot())], realtime=True)

if __name__ == "__main__":
    main()
