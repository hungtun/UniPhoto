import os
import sys
from pathlib import Path
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def is_packaged_runtime() -> bool:
    """Return True when running inside a PyInstaller bundle or with UNIPHOTO_PACKAGED=1."""
    return (
        bool(getattr(sys, "frozen", False))
        or os.environ.get("UNIPHOTO_PACKAGED", "").strip() == "1"
    )


def resolve_data_dir() -> Path:
    """Resolve writable application data directory without touching read-only app bundles."""
    env_data_dir = os.environ.get("UNIPHOTO_DATA_DIR", "").strip()
    if env_data_dir:
        return Path(env_data_dir).expanduser()

    if is_packaged_runtime():
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "com.hung.uniphoto"
        return Path.home() / ".uniphoto"

    return BASE_DIR / "data"


RESOLVED_DATA_DIR = resolve_data_dir()
DEFAULT_SQLITE_PATH = RESOLVED_DATA_DIR / "uniphoto.db"


class Settings(BaseSettings):
    PROJECT_NAME: str = "UniPhoto API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    DATA_DIR: str = Field(default_factory=lambda: str(resolve_data_dir()))
    BUNDLED_MODELS_DIR: str = Field(
        default_factory=lambda: os.environ.get("UNIPHOTO_MODELS_DIR", "").strip()
    )

    # Cấu hình kết nối SQLite
    SQLITE_DB_PATH: str = Field(
        default_factory=lambda: str(resolve_data_dir() / "uniphoto.db")
    )
    DATABASE_URL: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Khi chạy bản đóng gói (.app) hoặc có UNIPHOTO_DATA_DIR riêng, bỏ qua file .env cục bộ
        # để SQLITE_DB_PATH="data/uniphoto.db" trong .env không ghi đè thư mục dữ liệu chỉ định.
        if is_packaged_runtime() or os.environ.get("UNIPHOTO_DATA_DIR", "").strip():
            return (init_settings, env_settings, file_secret_settings)
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)

    @model_validator(mode="after")
    def _normalize_paths(self) -> "Settings":
        if self.DATA_DIR:
            self.DATA_DIR = str(Path(self.DATA_DIR).expanduser())
        if self.BUNDLED_MODELS_DIR:
            self.BUNDLED_MODELS_DIR = str(Path(self.BUNDLED_MODELS_DIR).expanduser())
        if (
            "DATA_DIR" in self.model_fields_set
            and "SQLITE_DB_PATH" not in self.model_fields_set
            and not os.environ.get("SQLITE_DB_PATH", "").strip()
        ):
            self.SQLITE_DB_PATH = str(Path(self.DATA_DIR) / "uniphoto.db")
        return self

    @property
    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        db_path = os.path.abspath(os.path.expanduser(self.SQLITE_DB_PATH))
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return f"sqlite:///{db_path}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
