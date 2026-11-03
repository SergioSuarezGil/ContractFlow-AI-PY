from contextlib import asynccontextmanager

from contractflow_observability.build_info import version_payload
from contractflow_observability.metrics import HttpMetricsMiddleware
from contractflow_shared import get_settings
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contracts_api.deps import (
    grpc_health_status,
    nest_readiness,
    shutdown_messaging,
    shutdown_persistence,
    startup_messaging,
    startup_persistence,
)
from contracts_api.domain.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from contracts_api.infrastructure.http.comparisons_router import (
    router as comparisons_router,
)
from contracts_api.infrastructure.http.contracts_router import router as contracts_router
from contracts_api.infrastructure.http.documents_router import router as documents_router
from contracts_api.infrastructure.http.internal_router import router as internal_router
from contracts_api.infrastructure.http.jobs_router import router as jobs_router
from contracts_api.infrastructure.http.metrics_router import router as metrics_router
from contracts_api.infrastructure.http.metrics_router import service_metrics
from contracts_api.infrastructure.http.nest_errors import nest_domain_error, nest_http_error
from contracts_api.infrastructure.http.reports_router import router as reports_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.auth_mode == "oidc" and not settings.oidc_audience.strip():
        raise RuntimeError("OIDC_AUDIENCE is required when AUTH_MODE=oidc")
    await startup_persistence()
    await startup_messaging()
    yield
    await shutdown_messaging()
    await shutdown_persistence()


app = FastAPI(
    title="ContractFlow Contracts API",
    version="0.1.0",
    description="Contracts, jobs, results consumer, and metrics",
    lifespan=lifespan,
)

app.include_router(contracts_router)
app.include_router(documents_router)
app.include_router(comparisons_router)
app.include_router(jobs_router)
app.include_router(reports_router)
app.include_router(metrics_router)
app.include_router(internal_router)
app.add_middleware(HttpMetricsMiddleware, metrics=service_metrics)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "contracts-api",
        "app": settings.app_name,
        "llmProvider": settings.llm_provider,
        "authMode": settings.auth_mode,
        "messaging": settings.messaging,
        "version": version_payload("contracts-api"),
    }


async def _ready_response() -> JSONResponse:
    status_code, body = await nest_readiness(grpc_status=await grpc_health_status())
    return JSONResponse(status_code=status_code, content=body)


@app.get("/health/ready")
async def health_ready() -> JSONResponse:
    return await _ready_response()


@app.get("/ready")
async def ready() -> JSONResponse:
    return await _ready_response()


@app.exception_handler(NotFoundError)
async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content=nest_domain_error(404, exc))


@app.exception_handler(ForbiddenError)
async def forbidden_handler(_request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content=nest_domain_error(403, exc))


@app.exception_handler(ValidationError)
async def validation_handler(_request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=nest_domain_error(422, exc))


@app.exception_handler(ConflictError)
async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content=nest_domain_error(409, exc))


@app.exception_handler(DomainError)
async def domain_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=400, content=nest_domain_error(400, exc))


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=nest_http_error(exc.status_code, exc.detail),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=nest_http_error(422, jsonable_encoder(exc.errors())),
    )


def run() -> None:
    import uvicorn

    uvicorn.run("contracts_api.main:app", host="0.0.0.0", port=3010, reload=False)


if __name__ == "__main__":
    run()
