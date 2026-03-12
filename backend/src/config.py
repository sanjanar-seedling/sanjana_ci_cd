from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hf_api_key: str = ""
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cicd_orchestrator"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
