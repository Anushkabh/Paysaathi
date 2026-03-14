from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    EXTERNAL_API_BASE_URL: str = "http://localhost:8001"
    DATABASE_URL: str = "sqlite:///./takaada.db"
    SYNC_INTERVAL_MINUTES: int = 30

    model_config = {"env_file": ".env"}


settings = Settings()
