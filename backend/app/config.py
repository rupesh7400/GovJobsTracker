from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://govjobs:govjobs@localhost:5432/govjobs"
    firebase_credentials: str = ""       # path to Firebase service-account JSON; empty = pushes queue up
    admin_api_key: str = ""              # REQUIRED for /admin and the dashboard
    token_secret: str = ""               # REQUIRED: signs app-user tokens
    user_agent: str = "GovJobsTracker/1.0 (contact: set-your-email@example.com)"
    request_timeout: int = 30
    max_failures_before_unavailable: int = 5
    max_pdf_mb: int = 25
    model_config = {"env_file": ".env"}

settings = Settings()
