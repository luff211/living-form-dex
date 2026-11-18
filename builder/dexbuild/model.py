"""Shared data shapes."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entry:
    method: str            # Wild, Static, Gift, In-game trade, Raid, Evolve, Breed, Form change, Event, GO, HOME gift
    place: str
    versions: tuple[str, ...]   # version codes this entry applies to; () for Other-column entries
    dlc: str | None = None
    ended: bool = False         # no longer obtainable by a new player
    unverified: bool = False    # depends on an unverified hand-kept fact
    note: str | None = None
    gender: str | None = None   # "m" / "f" when the source fixes gender
    needs_other_game: bool = False   # needs another game's save data or items; not obtainable starting this game alone


@dataclass
class Row:
    id: str
    dex: int
    name: str
    form_name: str
    species: int
    form: int
    gender: str | None          # "m" / "f" / None
    mega: list[str]
    gmax: bool
    gmax_unverified: bool
    cells: dict[str, list[Entry]] = field(default_factory=dict)   # group id -> entries, filled in Task 8
    other: list[Entry] = field(default_factory=list)


@dataclass(frozen=True)
class LeftOut:
    species: int
    form: int
    name: str
    form_name: str
    reason: str
    verified: bool
