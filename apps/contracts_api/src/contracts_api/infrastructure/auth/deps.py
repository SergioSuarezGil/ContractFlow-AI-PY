from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

import httpx
import jwt
from contractflow_shared import Settings, get_settings
from contracts_api.application.actor import ActorContext
from contracts_api.infrastructure.auth.jwt_actor import (
    InvalidJwtActorError,
    map_jwt_payload_to_actor,
)
from fastapi import Header, HTTPException, status
from jwt import PyJWKClient


def resolve_auth_mode(settings: Settings) -> str:
    mode = settings.auth_mode
    if mode == "dev":
        env = settings.environment.lower()
        if env not in {"development", "test"}:
            raise RuntimeError(
                "AUTH_MODE=dev is only allowed when ENVIRONMENT is development or test"
            )
        return "dev"
    if mode != "oidc":
        raise RuntimeError(f"Unsupported AUTH_MODE '{mode}'. Use 'oidc' or 'dev'.")
    if not settings.oidc_audience.strip():
        raise RuntimeError("OIDC_AUDIENCE is required when AUTH_MODE=oidc")
    return "oidc"


@lru_cache
def _jwks_client(jwks_uri: str) -> PyJWKClient:
    return PyJWKClient(jwks_uri)


async def get_actor(
    authorization: Annotated[str | None, Header()] = None,
    x_owner_id: Annotated[str | None, Header()] = None,
    x_household_id: Annotated[str | None, Header()] = None,
) -> ActorContext:
    settings = get_settings()
    mode = resolve_auth_mode(settings)
    if mode == "dev":
        return ActorContext(
            owner_id=(x_owner_id or settings.dev_owner_id).strip(),
            household_id=(x_household_id or settings.dev_household_id).strip(),
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty Bearer token",
        )

    try:
        signing_key = _jwks_client(settings.oidc_jwks_uri).get_signing_key_from_jwt(
            token
        )
        payload: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "sub"]},
        )
        return map_jwt_payload_to_actor(payload)
    except InvalidJwtActorError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    except (jwt.PyJWTError, httpx.HTTPError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc
