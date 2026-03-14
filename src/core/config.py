"""
Centralized configuration for the AI Job Application Agent.
Loads from config.json (preferences) and .env (secrets).
"""

import json
import os
import logging
from pydantic import BaseModel, Field
from typing import List

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.json")


class LLMSettings(BaseModel):
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"
    default_temperature: float = 0.1


class JobSearchSettings(BaseModel):
    search_keywords: str = (
        '"Solutions Architect" OR "GEN AI Architect" OR "AI Architect" '
        'OR "Technical Architect" OR "Agentic AI Architect"'
    )
    search_location: str = "India"
    job_limit: int = 3
    time_filter: str = "past_24_hours"  # "past_24_hours" or "past_week"


class RoleFilterSettings(BaseModel):
    architect_keywords: List[str] = Field(default_factory=lambda: [
        "solutions architect", "solution architect", "gen ai architect",
        "ai architect", "technical architect", "agentic ai architect"
    ])
    excluded_role_keywords: List[str] = Field(default_factory=lambda: [
        "engineer", "developer"
    ])
    require_top_tier_company: bool = True


class ProfileSettings(BaseModel):
    resume_path: str = "Phani_Kumar_Kolla_profile.pdf"
    linkedin_url: str = "https://www.linkedin.com/in/phanikumarkolla/"
    github_url: str = "https://github.com/phanikolla"


class NotificationSettings(BaseModel):
    receiver_email: str = "pkkolla24@gmail.com"
    email_subject: str = "Daily Agent Report: Tailored Job Applications Ready"
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587


class PDFSettings(BaseModel):
    page_format: str = "A4"
    margin: str = "0.75in"


class ApplySettings(BaseModel):
    applicant_profile_path: str = "applicant_profile.md"
    idle_timeout_minutes: int = 30


class AppConfig(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    job_search: JobSearchSettings = Field(default_factory=JobSearchSettings)
    role_filters: RoleFilterSettings = Field(default_factory=RoleFilterSettings)
    profile: ProfileSettings = Field(default_factory=ProfileSettings)
    notification: NotificationSettings = Field(default_factory=NotificationSettings)
    pdf: PDFSettings = Field(default_factory=PDFSettings)
    apply: ApplySettings = Field(default_factory=ApplySettings)
    output_dir: str = "output"


def load_config() -> AppConfig:
    """Load config from config.json, falling back to defaults."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            config = AppConfig(**data)
            logger.info(f"Config loaded from {CONFIG_FILE}")
            return config
        except Exception as e:
            logger.warning(f"Failed to load config from {CONFIG_FILE}: {e}. Using defaults.")
    else:
        logger.info(f"No config file found at {CONFIG_FILE}. Using defaults.")

    config = AppConfig()
    save_config(config)
    return config


def save_config(config: AppConfig) -> None:
    """Save config to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(), f, indent=2)
        logger.info(f"Config saved to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
