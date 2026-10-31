"""Operator-configured task limits and spoof-resistant anonymous admission."""

import hashlib
import ipaddress
from datetime import UTC, datetime

from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings
from app.engines.agent.actions import BUILTIN_TASKS, TASKS
from app.models.domain import AdmissionBucket

TASK_NAMES = {
    "FIND_PRICING": "Find pricing",
    "FIND_CONTACT": "Find contact info",
    "FIND_SIGNUP_FORM": "Reach signup form",
    "FIND_DOCUMENTATION": "Find documentation (legacy)",
}


def snapshot(settings: Settings):
    free = settings.agent_free_limits_enabled
    task_limit = settings.agent_free_task_limit if free else len(BUILTIN_TASKS)
    runs = (
        min(settings.agent_runs_per_task, settings.agent_free_runs_per_task)
        if free
        else settings.agent_runs_per_task
    )
    return {
        "version": "agent-v1",
        "pipeline_enabled": settings.agent_pipeline_enabled,
        "model_identifier": settings.agent_model,
        "task_types": list(BUILTIN_TASKS[:task_limit]),
        "task_limit": task_limit,
        "default_runs": runs,
        "runs_limit": settings.agent_free_runs_per_task if free else 3,
        "free_limits_enabled": free,
        "max_steps": settings.agent_max_steps,
        "duration_seconds": settings.agent_duration,
        "token_budget": settings.agent_token_budget,
        "action_delay": settings.agent_action_delay,
        "judge_enabled": settings.agent_judge_enabled,
        "score_weight": settings.agent_score_weight,
        "cost_rates": {
            "input": settings.agent_input_cost_per_million,
            "output": settings.agent_output_cost_per_million,
        },
        "stage_seconds": min(
            settings.agent_stage_duration, task_limit * runs * settings.agent_duration + 20
        ),
    }


def public_config(settings: Settings):
    policy = snapshot(settings)
    configured = bool(
        settings.agent_model
        and (
            settings.agent_llm_mode == "local"
            or settings.hf_token.get_secret_value()
            or settings.hf_tokens.get_secret_value()
        )
    )
    return {
        **{
            k: policy[k]
            for k in (
                "model_identifier",
                "max_steps",
                "duration_seconds",
                "token_budget",
                "action_delay",
                "default_runs",
                "runs_limit",
                "free_limits_enabled",
                "task_limit",
                "pipeline_enabled",
            )
        },
        "configured": configured,
        "max_runs": 3,
        "tasks": [
            {"task_type": task, "name": TASK_NAMES[task], "goal": TASKS[task]}
            for task in BUILTIN_TASKS
        ],
    }


def client_identity(request: Request, settings: Settings):
    peer = request.client.host if request.client else "unknown-peer"
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return peer[:100]
    networks = [ipaddress.ip_network(value) for value in settings.agent_trusted_proxy_cidrs]

    def trusted(ip):
        return any(ip in network for network in networks)

    if not trusted(address):
        return str(address)
    chain = request.headers.get("x-forwarded-for", "")
    if not chain or len(chain) > 512:
        return str(address)
    try:
        hops = [ipaddress.ip_address(value.strip()) for value in chain.split(",")]
    except ValueError:
        return str(address)
    if len(hops) > 10:
        return str(address)
    # Walk from the socket toward the origin; never trust addresses past the
    # first untrusted hop. Edge proxies must overwrite client-supplied chains.
    current = address
    for hop in reversed(hops):
        if not trusted(current):
            break
        current = hop
    return str(current)


def consume_admission(session, identity: str, operation: str, settings: Settings):
    now = datetime.now(UTC)
    seconds = settings.agent_ip_window_seconds
    start = int(now.timestamp()) // seconds * seconds
    expiry = datetime.fromtimestamp(start + seconds, UTC)
    hashed = hashlib.sha256(identity.encode()).hexdigest()
    key = f"{operation}:{start}:{hashed}"
    limit = settings.agent_ip_scan_limit if operation == "scan" else settings.agent_ip_task_limit
    expired = (
        select(AdmissionBucket.bucket_key).where(AdmissionBucket.expires_at <= now).limit(1000)
    )
    session.execute(delete(AdmissionBucket).where(AdmissionBucket.bucket_key.in_(expired)))
    statement = insert(AdmissionBucket).values(bucket_key=key, count=1, expires_at=expiry)
    count = session.scalar(
        statement.on_conflict_do_update(
            index_elements=[AdmissionBucket.bucket_key], set_={"count": AdmissionBucket.count + 1}
        ).returning(AdmissionBucket.count)
    )
    if count > limit:
        raise HTTPException(
            429,
            "Anonymous execution limit reached. Please retry after the current rate-limit window.",
        )
