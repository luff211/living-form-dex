"""Map PKHeX encounter type names to a method and an ended flag."""


class UnknownKind(Exception):
    pass


def _all(names, method, ended):
    return {n: (method, ended) for n in names.split()}


# Every type name PKHeX produces today, listed by hand. A new one raises UnknownKind until it is looked at.
_KINDS = {
    **_all("EncounterEgg2 EncounterEgg3 EncounterEgg4 EncounterEgg5 EncounterEgg6 EncounterEgg7 EncounterEgg8 "
           "EncounterEgg8b EncounterEgg9", "Breed", False),
    **_all("EncounterSlot7GO EncounterSlot8GO", "GO", False),
    **_all("EncounterSlot1 EncounterSlot2 EncounterSlot3 EncounterSlot3Swarm EncounterSlot4 EncounterSlot5 "
           "EncounterSlot6AO EncounterSlot6XY EncounterSlot7 EncounterSlot7b EncounterSlot8 EncounterSlot8a "
           "EncounterSlot8b EncounterSlot9 EncounterSlot9a", "Wild", False),
    "EncounterOutbreak9": ("Wild", True),             # distribution outbreaks
    "EncounterStatic4Pokewalker": ("Gift", False),
    "EncounterStatic5Entree": ("Static", True),       # Entree Forest (Dream World) is shut down
    "EncounterStatic5Radar": ("Static", True),        # Dream Radar is shut down
    "EncounterStatic8ND": ("Raid", True),             # distribution raid dens
    "EncounterStatic8N": ("Raid", False),             # stock raid dens
    "EncounterStatic8NC": ("Raid", True),             # Watchtower den: needs a Dynamax Crystal, given out by code in 2020
    **_all("EncounterDist9 EncounterMight9", "Raid", True),          # 7-star raids are time-limited events
    "EncounterTera9": ("Raid", False),
    **_all("EncounterStatic1 EncounterStatic2 EncounterStatic3 EncounterStatic4 EncounterStatic5 EncounterStatic5N "
           "EncounterStatic6 EncounterStatic7 EncounterStatic7b EncounterStatic8 EncounterStatic8U EncounterStatic8a "
           "EncounterStatic8b EncounterStatic9 EncounterStatic9a EncounterFixed9", "Static", False),
    "EncounterTrade4RanchGift": ("Gift", True),       # My Pokémon Ranch is shut down
    **_all("EncounterTrade1 EncounterTrade2 EncounterTrade3 EncounterTrade4PID EncounterTrade5B2W2 EncounterTrade5BW "
           "EncounterTrade6 EncounterTrade7 EncounterTrade7b EncounterTrade8 EncounterTrade8b EncounterTrade9 "
           "EncounterTrade9a", "In-game trade", False),
    # distributions, not in-game gifts
    **_all("EncounterGift1 EncounterGift3 EncounterGift3Colo EncounterGift3JPN EncounterGift3NY", "Event", True),
    "EncounterGift9a": ("Gift", False),
    **_all("PCD PGF PGT WA8 WA9 WB7 WB8 WC6 WC7 WC8 WC9", "Event", True),
}


def method_for(type_name: str, label: str) -> tuple[str, bool]:
    try:
        return _KINDS[type_name]
    except KeyError:
        raise UnknownKind(f"no method for encounter type {type_name!r} (label {label!r}); "
                          "add it to builder/dexbuild/kinds.py") from None
