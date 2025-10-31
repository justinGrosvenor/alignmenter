"""Application settings using Pydantic."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


class Settings(BaseSettings):
    """Runtime configuration for Alignmenter."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)
    openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "ALIGNMENTER_OPENAI_API_KEY"),
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "ALIGNMENTER_ANTHROPIC_API_KEY"),
    )
    default_model: str = Field(
        default="openai:gpt-4o-mini",
        validation_alias=AliasChoices("ALIGNMENTER_DEFAULT_MODEL"),
    )
    embedding_provider: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_EMBEDDING_PROVIDER"),
    )
    default_dataset: str = Field(
        default=str(PROJECT_ROOT / "datasets" / "demo_conversations.jsonl"),
        validation_alias=AliasChoices("ALIGNMENTER_DEFAULT_DATASET"),
    )
    default_persona: str = Field(
        default=str(PROJECT_ROOT / "configs" / "persona" / "default.yaml"),
        validation_alias=AliasChoices("ALIGNMENTER_DEFAULT_PERSONA"),
    )
    default_keywords: str = Field(
        default=str(PROJECT_ROOT / "configs" / "safety_keywords.yaml"),
        validation_alias=AliasChoices("ALIGNMENTER_DEFAULT_KEYWORDS"),
    )
    judge_provider: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_JUDGE_PROVIDER"),
    )
    judge_budget: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_JUDGE_BUDGET"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
