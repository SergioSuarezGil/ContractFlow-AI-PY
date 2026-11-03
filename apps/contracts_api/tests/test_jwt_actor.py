import pytest
from contracts_api.infrastructure.auth.jwt_actor import (
    InvalidJwtActorError,
    map_jwt_payload_to_actor,
)


def test_uses_sub_as_owner_id() -> None:
    actor = map_jwt_payload_to_actor({"sub": "uuid-123", "household_id": "hh_demo"})
    assert actor.owner_id == "uuid-123"
    assert actor.household_id == "hh_demo"


def test_defaults_household_from_sub() -> None:
    actor = map_jwt_payload_to_actor({"sub": "uuid-123"})
    assert actor.household_id == "hh_uuid-123"


def test_rejects_missing_sub() -> None:
    with pytest.raises(InvalidJwtActorError):
        map_jwt_payload_to_actor({})
