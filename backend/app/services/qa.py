"""Phase 4: run QA tasks with Gemini Computer Use on the original site and on the
agent variant, verify answers with rules, and store the comparison.

Original runs use a normal browser identity, which the edge router passes through to
the origin. Variant runs use the AgentLane-QA agent identity, which the router serves
the published variant. Infrastructure problems are ERROR and excluded from rates.
"""

import asyncio
import time
from urllib.parse import urlsplit
from uuid import uuid4

from app.core.config import Settings
from app.edge.agents import QA_AGENT
from app.engines.agent.provider import InferenceError
from app.engines.qa.computer_use import run_task
from app.engines.qa.tasks import SUITES
from app.engines.variants.evidence import open_page, origin_of
from app.models.domain import QARun
from app.repositories.edge import EdgeRecords
from app.repositories.insights import InsightRecords
from app.services.edge_sites import normalize_host
from app.services.insights import qa_summary

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
AGENT_UA = f"Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; {QA_AGENT}/1.0"
TARGETS = {"original": BROWSER_UA, "variant": AGENT_UA}


async def _one_run(base_url: str, task, user_agent: str, settings: Settings):
    async with asyncio.timeout(settings.qa_task_timeout + 30):
        async with open_page(
            origin_of(base_url), settings, request_limit=800, user_agent=user_agent, get_only=False
        ) as (page, navigate):
            return await run_task(page, navigate, base_url, task.prompt, settings)


async def run_qa(
    host: str,
    base_url: str,
    settings: Settings,
    session_factory,
    suite: str = "demo-store",
    task_keys: list[str] | None = None,
    targets: tuple[str, ...] = ("original", "variant"),
) -> dict:
    if not settings.gemini_api_key.get_secret_value():
        raise InferenceError("Configure GEMINI_API_KEY for Computer Use QA")
    tasks = [t for t in SUITES[suite] if not task_keys or t.key in task_keys]
    with session_factory() as session:
        site = EdgeRecords(session).site_by_host(normalize_host(host))
        if site is None:
            raise ValueError(f"{host} is not registered")
        if (urlsplit(base_url).hostname or "").lower() != site.host:
            raise ValueError("The base URL must use the registered public host")
        site_id = site.id
    batch_id = uuid4()
    for target in targets:
        for task in tasks:
            started = time.monotonic()
            outcome, detail, result = "ERROR", None, None
            try:
                result = await _one_run(base_url, task, TARGETS[target], settings)
                if result.answer and task.verify(result.answer):
                    outcome = "PASSED"
                elif result.error and "confirmation" in result.error:
                    detail = result.error  # Safety stop: excluded, never auto-confirmed.
                else:
                    outcome, detail = "FAILED", result.error or "Answer did not match"
            except (InferenceError, TimeoutError, ValueError, OSError) as exc:
                detail = f"{type(exc).__name__}: {exc}"[:300]
            with session_factory() as session:
                session.add(
                    QARun(
                        site_id=site_id,
                        batch_id=batch_id,
                        task_key=task.key,
                        task_prompt=task.prompt,
                        target=target,
                        outcome=outcome,
                        answer=(result.answer or "")[:2000] if result else None,
                        detail=detail[:300] if detail else None,
                        steps=result.steps if result else 0,
                        input_tokens=result.input_tokens if result else 0,
                        output_tokens=result.output_tokens if result else 0,
                        duration_ms=int((time.monotonic() - started) * 1000),
                        model=settings.qa_model,
                    )
                )
                session.commit()
    with session_factory() as session:
        return qa_summary(InsightRecords(session).latest_qa_batch(site_id))
