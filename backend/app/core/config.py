from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    sec_api_key: str = ""
    sec_api_base_url: str = "https://api.sec.or.th"
    data_dir: Path = Path("data")
    sec_cache_dir: Path = Path("data/sec")
    # Comma-separated list of allowed CORS origins. "*" (the default) permits
    # any origin -- safe here because this API has no cookies/sessions to
    # steal, and it means a deployer who never touches this env var still
    # gets a working app instead of a same-origin-only failure out of the box.
    allowed_origins: str = "*"

    def allowed_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        return origins or ["*"]


settings = Settings()
