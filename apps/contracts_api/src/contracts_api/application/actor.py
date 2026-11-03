from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActorContext:
    owner_id: str
    household_id: str
