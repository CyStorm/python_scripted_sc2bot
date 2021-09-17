from sc2.ids.unit_typeid import UnitTypeId as UNITID
from sc2.ids.ability_id import AbilityId as ABILITYID
from sc2.ids.buff_id import BuffId as BUFFID
from sc2.ids.upgrade_id import UpgradeId as UPGRADEID


ground_army = [UNITID.STALKER, UNITID.ZEALOT]
air_army = [UNITID.PHOENIX, UNITID.STALKER]

Hard_Counters = {
    UNITID.STALKER: [UNITID.MARAUDER, UNITID.IMMORTAL, UNITID.LURKER],
}
