from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./nlti.db"
    nlti_env: str = "development"
    secret_key: str = "development-only-not-for-production"
    access_token_minutes: int = 45
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
