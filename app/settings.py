import os
from pathlib import Path

# from pydantic import BaseSettings
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    LOG_LEVEL: str
    DEBUG: bool = False

    class Config:
        env = os.environ["APP_CONFIG_FILE"]
        env_file = Path(__file__).parent / f"config/{env}.env"
        case_sensitive = True
