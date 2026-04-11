from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    host: str = "0.0.0.0"
    port: int = 8000
    app_base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
