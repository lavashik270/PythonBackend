from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DIR = Path(__file__).absolute().parent.parent.parent
APP_DIR = Path(__file__).absolute().parent.parent
TEMP_DIR = f"{APP_DIR}/temp"
UPLOAD_DIR = f"{TEMP_DIR}/upload"


class EnvBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class S3Settings(EnvBaseSettings):
    S3_BUCKET: str
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_ACCESS_KEY: str
    S3_REGION: str = 'ru-1'


class Settings(S3Settings):
    pass


settings = Settings()
