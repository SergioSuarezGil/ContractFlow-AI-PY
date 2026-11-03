from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AuthMode = Literal["oidc", "dev"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "contractflow-ai-py"
    environment: str = "development"
    llm_provider: str = "mock"
    auth_mode: AuthMode = "oidc"
    oidc_issuer: str = "http://localhost:8080/realms/contractflow"
    oidc_jwks_uri: str = (
        "http://localhost:8080/realms/contractflow/protocol/openid-connect/certs"
    )
    oidc_audience: str = "contractflow-web"
    dev_owner_id: str = "demo"
    dev_household_id: str = "hh_demo"
    mongodb_uri: str = "mongodb://localhost:27017/contractflow?directConnection=true"
    mongodb_db: str = "contractflow"
    contracts_repo: Literal["memory", "mongo"] = "memory"
    object_storage: Literal["memory", "s3"] = "memory"
    messaging: Literal["noop", "rabbit"] = "noop"
    rabbitmq_url: str = "amqp://contractflow:contractflow@localhost:5672"
    rabbitmq_exchange: str = "contractflow.events"
    s3_bucket_documents: str = "documents"
    s3_bucket_reports: str = "reports"
    s3_endpoint: str = "localhost"
    s3_port: int = 4566
    s3_use_ssl: bool = False
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_force_path_style: bool = True
    ai_worker_grpc_target: str = ""
    outbox_poll_ms: int = 500
    outbox_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
