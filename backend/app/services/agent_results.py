"""Deterministic aggregation and score blending, separate from inference."""


def eligible(run):
    if run.failure_category == "infra_error" or run.outcome in (
        None,
        "UNAVAILABLE",
        "INCONCLUSIVE",
    ):
        return False
    return run.outcome == "FAILED" or run.verification_method in ("rules", "judged")


def aggregate(runs):
    terminal = [run for run in runs if run.status.value in ("COMPLETED", "FAILED")]
    valid = [run for run in terminal if eligible(run)]
    successes = sum(run.outcome == "SUCCEEDED" for run in valid)
    failures = len(valid) - successes
    if not valid:
        outcome = (
            "UNAVAILABLE"
            if terminal
            and all(
                run.failure_category == "infra_error" or run.outcome == "UNAVAILABLE"
                for run in terminal
            )
            else "INCONCLUSIVE"
        )
    elif successes == failures:
        outcome = "INCONCLUSIVE"
    else:
        outcome = "SUCCEEDED" if successes > failures else "FAILED"
    return {
        "outcome": outcome,
        "consistency": len({run.outcome for run in valid}) == 1 if len(valid) >= 2 else None,
        "eligible_runs": len(valid),
        "runs_completed": len(terminal),
        "success_rate": successes / len(valid) if valid else None,
    }


def blend(static_score, tasks, weight):
    rates = []
    eligible_count = unavailable = inconclusive = judged = eligible_tasks = 0
    incomplete_tasks = 0
    task_results = []
    for task, runs in tasks:
        result = aggregate(runs)
        status = getattr(task, "status", "COMPLETED")
        status = getattr(status, "value", status)
        terminal = status in ("COMPLETED", "FAILED")
        if not terminal:
            incomplete_tasks += 1
        else:
            eligible_count += result["eligible_runs"]
            unavailable += sum(
                run.failure_category == "infra_error" or run.outcome == "UNAVAILABLE"
                for run in runs
            )
            inconclusive += sum(run.outcome == "INCONCLUSIVE" for run in runs)
            judged += sum(eligible(run) and run.verification_method == "judged" for run in runs)
            # Score the configured task-level majority. A repeat tie stays
            # inconclusive instead of being converted to a fractional pass.
            if result["outcome"] in ("SUCCEEDED", "FAILED"):
                rates.append(float(result["outcome"] == "SUCCEEDED"))
                eligible_tasks += 1
        task_results.append({"task_type": task.task_type, **result, "status": status})
    agent_score = round(100 * sum(rates) / len(rates), 1) if rates else None
    effective = (
        weight
        if static_score is not None and agent_score is not None
        else (1.0 if agent_score is not None else 0.0)
    )
    if agent_score is None:
        score = static_score
        fallback = (
            "Agent test unavailable: only infrastructure errors occurred."
            if unavailable and not inconclusive
            else "Agent results are not conclusive or have not run; using the static score."
        )
    elif static_score is None:
        score, fallback = (
            agent_score,
            "Static score unavailable; agent-only evidence is shown with limited coverage.",
        )
    else:
        score = round(static_score * (1 - weight) + agent_score * weight, 1)
        fallback = None
    return {
        "version": "agent-v1",
        "score": score,
        "static_score": static_score,
        "agent_score": agent_score,
        "configured_weight": weight,
        "effective_weight": effective,
        "eligible_runs": eligible_count,
        "eligible_tasks": eligible_tasks,
        "incomplete_tasks": incomplete_tasks,
        "excluded_infra_runs": unavailable,
        "inconclusive_runs": inconclusive,
        "judged_runs": judged,
        "tasks": task_results,
        "fallback_reason": fallback,
        "provisional": bool(unavailable or inconclusive or judged or incomplete_tasks),
        "score_kind": "COMBINED_READINESS"
        if static_score is not None and agent_score is not None
        else ("AGENT_READINESS" if agent_score is not None else "STATIC_READINESS"),
    }
