from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_AMBIGUITY_MODEL: str = "openai/gpt-oss-20b"  # cheaper/faster model

    COHERE_API_KEY: str = ""
    COHERE_EMBED_MODEL: str = "embed-english-v3.0"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/contract_reviewer"
    API_KEY: str = ""

settings = Settings()