from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application configuration, loaded from environment variables
    (or a local .env file). See .env.example for the full list of keys.
    """

    # Core
    database_url: str = "sqlite:///./finance.db"

    # Create tables straight from the models on startup. Convenient for SQLite
    # and tests, but turn this OFF against a real database (Supabase/Postgres)
    # and use Alembic instead -- create_all never alters an existing table, so
    # schema changes would otherwise be silently ignored.
    db_auto_create_tables: bool = True
    # Connection pool. Supabase's pooler closes idle connections, so
    # pool_pre_ping is enabled unconditionally for non-SQLite URLs.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle_seconds: int = 1800

    secret_key: str = "dev-secret-key-change-me"

    # JWT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Local LLM via Ollama (https://ollama.com). No API key and no outbound
    # network calls -- the model runs on this machine. The assistant endpoint
    # falls back to a rule-based reply if Ollama is unreachable.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"
    ollama_timeout_seconds: int = 120
    # 0.0 -- this assistant reports figures, so take the most likely token
    # rather than sampling. Raise slightly if replies feel robotic.
    ollama_temperature: float = 0.0

    # CORS
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
