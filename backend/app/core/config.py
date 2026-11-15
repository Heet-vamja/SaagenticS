from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Optional cost-rate variables may be present but intentionally blank in
    # local .env files. Treat those as unset instead of failing startup.
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore", env_ignore_empty=True)

    app_environment: Literal["development", "test", "production"] = "production"
    dev_email_shortcut_enabled: bool = False
    dev_access_email: str = ""
    customer_mode_enabled: bool = True
    verification_secret: SecretStr = SecretStr("")
    verification_cookie_secure: bool = True
    public_site_url: str = "http://localhost:3000"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(465, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = ""
    smtp_starttls: bool = False
    stripe_secret_key: SecretStr = SecretStr("")
    stripe_webhook_secret: SecretStr = SecretStr("")
    stripe_live_mode: bool = False
    paid_report_days: int = Field(365, ge=30, le=3650)

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
    audit_resource_limit: int = Field(5, ge=0, le=10)
    audit_diagnostics_timeout: float = Field(15, gt=0, le=30)
    audit_missing_path_enabled: bool = True
    report_share_days: int = Field(7, ge=1, le=30)

    hf_token: SecretStr = SecretStr("")
    hf_tokens: SecretStr = SecretStr("")
    osaurus_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    agent_llm_provider: Literal["gemini", "osaurus", "huggingface"] = "huggingface"
    agent_model: str = "Qwen/Qwen3-4B-Instruct-2507"
    agent_llm_mode: Literal["hosted", "local"] = "hosted"
    agent_llm_base_url: str = "https://router.huggingface.co/v1"
    agent_llm_timeout: float = Field(25, gt=0, le=120)
    agent_llm_retries: int = Field(2, ge=0, le=2)
    agent_structured_output: bool = False
    agent_max_output_tokens: int = Field(700, ge=100, le=1500)
    agent_max_steps: int = Field(15, ge=1, le=15)
    agent_duration: float = Field(90, gt=0, le=120)
    agent_invalid_limit: int = Field(3, ge=1, le=3)
    agent_observation_chars: int = Field(12000, ge=4000, le=20000)
    agent_max_elements: int = Field(150, ge=1, le=150)
    agent_request_limit: int = Field(150, ge=1, le=300)
    agent_max_redirects: int = Field(5, ge=0, le=5)
    agent_screenshot_dir: str = "./artifacts/agent"
    agent_screenshots: bool = True
    agent_browser_executable: str | None = None
    agent_pipeline_enabled: bool = False
    agent_runs_per_task: int = Field(2, ge=1, le=3)
    agent_free_limits_enabled: bool = True
    agent_free_task_limit: int = Field(2, ge=1, le=2)
    agent_free_runs_per_task: int = Field(1, ge=1, le=1)
    agent_token_budget: int = Field(32768, ge=1000, le=200000)
    agent_action_delay: float = Field(1, ge=1, le=10)
    agent_judge_enabled: bool = True
    agent_score_weight: float = Field(0.45, ge=0, le=1)
    agent_input_cost_per_million: float | None = Field(None, ge=0)
    agent_output_cost_per_million: float | None = Field(None, ge=0)
    agent_stage_duration: float = Field(600, ge=10, le=1800)
    agent_max_active: int = Field(2, ge=1, le=8)
    agent_ip_window_seconds: int = Field(3600, ge=60, le=86400)
    agent_ip_scan_limit: int = Field(10, ge=1, le=1000)
    agent_ip_task_limit: int = Field(20, ge=1, le=2000)
    agent_trusted_proxy_cidrs: list[str] = []
    # Edge router. Private origins are only for local Docker development (the demo store).
    edge_allow_private_origins: bool = False
    edge_upstream_timeout: float = Field(30, gt=0, le=120)
    # Owner dashboard API (phase 3). Disabled unless a token is configured.
    edge_dashboard_token: SecretStr = SecretStr("")
    # Agent variant generation (crawl, Gemini extraction, render). Separate budgets from
    # per-step agent inference because one extraction reads many pages at once.
    variant_max_pages: int = Field(50, ge=1, le=200)
    variant_crawl_duration: float = Field(180, gt=0, le=900)
    variant_page_chars: int = Field(12000, ge=1000, le=50000)
    variant_evidence_chars: int = Field(240000, ge=10000, le=1000000)
    variant_token_budget: int = Field(400000, ge=10000, le=2000000)
    variant_max_output_tokens: int = Field(16000, ge=1000, le=65536)
    variant_llm_timeout: float = Field(180, gt=0, le=600)
    # Agent QA with Gemini Computer Use (phase 4; native Gemini API only).
    qa_model: str = "gemini-3.8-flash"
    qa_max_steps: int = Field(20, ge=1, le=60)
    qa_task_timeout: float = Field(150, gt=0, le=900)
    # Public router URL QA uses for a host. Local Docker: http://{host}:8080.
    qa_base_url_template: str = Field("https://{host}", pattern=r"^https?://\{host\}(:\d{1,5})?$")
    # Local development only: Chromium host-resolver rules for the contained dev browser,
    # e.g. "MAP *.localhost edge" so the jobs worker reaches the router by its public name.
    dev_browser_host_rules: str = Field("", max_length=200)
    # Jobs worker (phase 5): dashboard-started builds, labeling and QA.
    jobs_poll_interval: float = Field(3, gt=0, le=60)
    job_max_duration: float = Field(3600, ge=60, le=14400)


@lru_cache
def get_settings() -> Settings:
    return Settings()
