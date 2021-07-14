from sc2.ids.ability_id import AbilityId as ABILITYID

class EconomyMicro():
    '''The economy micro methods
    '''

    def watch_gas_saturation(self):
        '''Handles the gas saturaion of gases by each building
        '''
        for assimilator in self.gas_buildings:
            # check each assimilator for over/underaturation
            # case of want full saturation
            diff = assimilator.assigned_harvesters - assimilator.ideal_harvesters
            if (diff > 0):
                worker = self.workers.closest_to(assimilator.position)
                worker.gather(self.owned_minerals.closest_to(worker.position))
                break
            elif (diff < 0):
                worker = self.workers.filter(lambda worker: worker.is_carrying_minerals).closest_to(assimilator.position)
                worker.gather(assimilator)
                break

    def watch_mineral_saturation(self):
        '''Optimize mineral saturaton, from oversaturation in bases and iterate though each base
        '''
        if (self.townhalls.ready.amount == 1):
            return
        unfilled_bases = self.townhalls.ready.filter(lambda base: base.assigned_harvesters < base.ideal_harvesters)
        oversaturated_bases = self.townhalls.ready.filter(lambda base: base.assigned_harvesters > base.ideal_harvesters)
        if (unfilled_bases):
            for nexus in oversaturated_bases:
                diff = nexus.assigned_harvesters - nexus.ideal_harvesters
                if (diff > 0):
                    nexus(ABILITYID.RALLY_NEXUS, self.owned_minerals.closest_to(unfilled_bases.random.position))
                    extra_workers = self.workers.closer_than(8, nexus.position).filter(lambda worker: worker.is_carrying_minerals).random_group_of(diff)
                    mineral = self.owned_minerals.closest_to(unfilled_bases.random.position)
                    for worker in extra_workers:
                        worker.gather(mineral, queue=True)
