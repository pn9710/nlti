from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./nlti.db"
    nlti_env: str = "development"
    secret_key: str = "development-only-not-for-production"
    access_token_minutes: int = 45
    document_store_path: str = "data/public-documents"
    public_app_url: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None
    smtp_starttls: bool = True
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def require_production_secret(self):
        if self.nlti_env.casefold() == "production" and (
            self.secret_key == "development-only-not-for-production"
            or len(self.secret_key) < 32
        ):
            raise ValueError("Set a unique NLTI_SECRET_KEY of at least 32 characters in production.")
        return self


settings = Settings()
