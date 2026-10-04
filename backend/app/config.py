from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://desk:desk@localhost:5432/desk"
    secret_key: str = "dev-only-change-me"
    access_token_minutes: int = 60 * 12
    seed_users_path: str = "/seed/users.json"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"


settings = Settings()
