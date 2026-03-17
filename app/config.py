"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_base_url: str = "http://localhost:8000"

    ecwid_app_id: str = ""
    ecwid_client_secret: str = ""

    kwtsms_api_base_url: str = "https://www.kwtsms.com/API"
    kwtsms_default_username: str = ""
    kwtsms_default_password: str = ""

    encryption_key: str

    database_path: str = "./data/kwtsms_ecwid.db"

    sync_hour: int = 3
    sync_minute: int = 0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


# kwtSMS rate limits
KWTSMS_RATE_LIMIT_SECONDS = 0.5
KWTSMS_BATCH_SIZE = 200
KWTSMS_BATCH_DELAY = 0.2
KWTSMS_MIN_SEND_INTERVAL = 15

# Ecwid API
ECWID_API_BASE = "https://app.ecwid.com/api/v3"
ECWID_WEBHOOK_CONNECT_TIMEOUT = 3
ECWID_WEBHOOK_RESPONSE_TIMEOUT = 10
ECWID_API_RATE_LIMIT = 600

# SMS encoding
SMS_PAGE_SIZE_EN = 160
SMS_PAGE_SIZE_AR = 70
SMS_CONCAT_PAGE_SIZE_EN = 153
SMS_CONCAT_PAGE_SIZE_AR = 67

# Misc
TIMEZONE_KWTSMS = "Asia/Kuwait"
MAX_ADMIN_PHONES = 5
