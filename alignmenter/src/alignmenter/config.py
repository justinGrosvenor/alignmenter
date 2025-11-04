"""Application settings using Pydantic."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent
REPO_ROOT = SOURCE_ROOT.parent if SOURCE_ROOT.name == "src" else SOURCE_ROOT
PROJECT_ROOT = REPO_ROOT
DATA_DIR = PACKAGE_ROOT / "data"


class Settings(BaseSettings):
    """Runtime configuration for Alignmenter."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT.parent / ".env"),
        extra="ignore",
        case_sensitive=False,
    )
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
        default=str(DATA_DIR / "datasets" / "demo_conversations.jsonl"),
        validation_alias=AliasChoices("ALIGNMENTER_DEFAULT_DATASET"),
    )
    default_persona: str = Field(
        default=str(DATA_DIR / "configs" / "persona" / "default.yaml"),
        validation_alias=AliasChoices("ALIGNMENTER_DEFAULT_PERSONA"),
    )
    default_keywords: str = Field(
        default=str(DATA_DIR / "configs" / "safety_keywords.yaml"),
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
    judge_budget_usd: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_JUDGE_BUDGET_USD"),
    )
    judge_price_per_1k_input: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_JUDGE_PRICE_PER_1K_INPUT"),
    )
    judge_price_per_1k_output: Optional[float] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_JUDGE_PRICE_PER_1K_OUTPUT"),
    )
    judge_estimated_tokens_per_call: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_JUDGE_ESTIMATED_TOKENS_PER_CALL"),
    )
    judge_estimated_prompt_tokens_per_call: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_JUDGE_ESTIMATED_PROMPT_TOKENS"),
    )
    judge_estimated_completion_tokens_per_call: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_JUDGE_ESTIMATED_COMPLETION_TOKENS"),
    )
    custom_gpt_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("ALIGNMENTER_CUSTOM_GPT_ID"),
    )
    safety_classifier: Optional[str] = Field(
        default="auto",
        validation_alias=AliasChoices("ALIGNMENTER_SAFETY_CLASSIFIER"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
