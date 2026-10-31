from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://agentreadiness:local-development-only@localhost:5432/agentreadiness"
    )
    cors_origins: list[str] = ["http://localhost:3000"]

    crawl_max_pages: int = Field(20, ge=1, le=1000)
    crawl_max_depth: int = Field(3, ge=0, le=10)
    crawl_request_timeout: float = Field(10, gt=0, le=60)
    crawl_max_redirects: int = Field(5, ge=0, le=10)
    crawl_sitemap_entries: int = Field(500, ge=1, le=10000)
    crawl_sitemap_depth: int = Field(3, ge=0, le=10)
    crawl_html_bytes: int = Field(2 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    crawl_sitemap_bytes: int = Field(2 * 1024 * 1024, ge=1, le=10 * 1024 * 1024)
    crawl_concurrency: int = Field(3, ge=1, le=10)
    crawl_duration: float = Field(300, gt=0, le=3600)
    crawl_min_delay: float = Field(0.1, ge=0, le=10)
    crawl_user_agent: str = "AgentReadinessBot/0.1"
    crawl_allow_subdomains: bool = False

    scan_duration: float = Field(120, ge=10, le=600)
    scan_max_active: int = Field(2, ge=1, le=8)
    scan_queue_limit: int = Field(30, ge=1, le=200)
    scan_queue_wait: float = Field(600, ge=30, le=3600)
    audit_render_pages: int = Field(3, ge=0, le=10)
    audit_render_timeout: float = Field(8, gt=0, le=20)
    audit_browser_enabled: bool = True
    report_share_days: int = Field(7, ge=1, le=30)

    hf_token: SecretStr = SecretStr("")
    hf_tokens: SecretStr = SecretStr("")
    agent_model: str = "Qwen/Qwen3-4B-Instruct-2507"
    agent_llm_mode: Literal["hosted", "local"] = "hosted"
    agent_llm_base_url: str = "https://router.huggingface.co/v1"
    agent_llm_timeout: float = Field(25, gt=0, le=60)
    agent_llm_retries: int = Field(2, ge=0, le=2)
    agent_structured_output: bool = False
    agent_max_output_tokens: int = Field(700, ge=100, le=1500)
    agent_max_steps: int = Field(15, ge=1, le=15)
    agent_duration: float = Field(120, gt=0, le=120)
    agent_invalid_limit: int = Field(3, ge=1, le=3)
    agent_observation_chars: int = Field(12000, ge=4000, le=20000)
    agent_max_elements: int = Field(60, ge=1, le=100)
    agent_request_limit: int = Field(150, ge=1, le=300)
    agent_max_redirects: int = Field(5, ge=0, le=5)
    agent_screenshot_dir: str = "./artifacts/agent"
    agent_screenshots: bool = True
    agent_browser_executable: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
