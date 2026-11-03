from typing import Any

from contracts_api.application.actor import ActorContext


class InvalidJwtActorError(ValueError):
    pass


def map_jwt_payload_to_actor(payload: dict[str, Any]) -> ActorContext:
    owner_id = str(payload.get("sub") or "").strip()
    if not owner_id:
        raise InvalidJwtActorError("Token missing subject (sub)")
    household_claim = payload.get("household_id")
    if isinstance(household_claim, list):
        household_id = str(household_claim[0] if household_claim else "").strip()
    else:
        household_id = str(household_claim or "").strip()
    return ActorContext(
        owner_id=owner_id,
        household_id=household_id or f"hh_{owner_id}",
    )
