"""
Configuration management for CBT Chat Assistant backend.
Loads settings from environment variables.
"""

from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=True, alias="DEBUG")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
        alias="CORS_ORIGINS"
    )

    # Supabase
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_key: str = Field(..., alias="SUPABASE_KEY")
    supabase_service_key: str = Field(..., alias="SUPABASE_SERVICE_KEY")

    # LLM APIs
    deepseek_api_key: str = Field(..., alias="DEEPSEEK_API_KEY")
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # LLM Configuration
    primary_llm: str = Field(default="deepseek", alias="PRIMARY_LLM")
    risk_detection_llm: str = Field(default="claude", alias="RISK_DETECTION_LLM")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    claude_model: str = Field(
        default="claude-3-5-haiku-20241022",
        alias="CLAUDE_MODEL"
    )

    # Risk Detection
    risk_detection_enabled: bool = Field(default=True, alias="RISK_DETECTION_ENABLED")
    auto_flag_therapist: bool = Field(default=True, alias="AUTO_FLAG_THERAPIST")

    # Session Configuration
    max_session_length_minutes: int = Field(
        default=60,
        alias="MAX_SESSION_LENGTH_MINUTES"
    )
    conversation_history_limit: int = Field(
        default=50,
        alias="CONVERSATION_HISTORY_LIMIT"
    )

    # Prompt configuration
    prompts_file: str = Field(
        default="config/prompts.yaml",
        alias="PROMPTS_FILE"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
