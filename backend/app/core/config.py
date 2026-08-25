from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./dash2bi.db"
    MAX_UPLOAD_SIZE_MB: int = 25
    UPLOAD_DIR: str = "./uploads"
    OUTPUT_DIR: str = "./outputs"

    AI_PROVIDER: str = "none"  # "anthropic" | "none"
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-6"

    FRONTEND_ORIGIN: str = "http://localhost:5173"

    class Config:
        env_file = ".env"

    def ensure_dirs(self):
        Path(self.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
