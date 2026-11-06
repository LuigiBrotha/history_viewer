from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[".env", ".env.local"], case_sensitive=True)

    APP_NAME: str = "Uboats"
    APP_VERSION: str = "0.0.1"
    DESCRIPTION: str = "Applicatie voor het scrapen van uboat.net"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./uboats.db"

    BASE_URL: str
    ROOT_PATH: str

    BASE_DIR: str
    HTTP_DIR: str

    CRAWLER_CONTACT: str = ""
    CRAWL_DELAY_SECONDS: float = 10.0

    WIKI_IMAGE_DIR: str = "~/.cache/uboats/wikipedia/images"


settings = Settings()
