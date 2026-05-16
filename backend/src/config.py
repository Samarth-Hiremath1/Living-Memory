from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    elevenlabs_voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # default: Bella
    aviationstack_api_key: str = ""

    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    graph_store_path: str = "./data/graph_store.json"

    # Model config
    orchestrator_model: str = "claude-sonnet-4-5"
    fast_model: str = "claude-haiku-4-5-20251001"


settings = Settings()
