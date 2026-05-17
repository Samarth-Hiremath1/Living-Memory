from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""  # Welcome Ambassador
    elevenlabs_assistant_agent_id: str = ""  # General Assistance / PlaceMaker Engine
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # default: Bella
    aviationstack_api_key: str = ""
    github_token: str = ""  # Optional — raises rate limit from 60 to 5,000 req/hr

    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    graph_store_path: str = "./data/graph_store.json"

    # Model config
    orchestrator_model: str = "claude-sonnet-4-5"
    fast_model: str = "claude-haiku-4-5"


settings = Settings()
