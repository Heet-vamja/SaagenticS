"""Gemini Computer Use driver (native Interactions API) for agent QA.

The model sees screenshots and returns UI actions with coordinates normalized to 0-999.
We execute them in our own browser, which is limited to the site under test, and send
back a screenshot plus the current URL. The run ends when the model answers in text, a
step or time limit is reached, or the model asks for a confirmation (we never confirm).
"""

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from playwright.async_api import Error as PlaywrightError

from app.core.config import Settings
from app.engines.agent.provider import InferenceError
from app.engines.variants.evidence import origin_of

ENDPOINT = "https://generativelanguage.googleapis.com/v1/interactions"
VIEWPORT = (1280, 800)
INSTRUCTIONS = """You are an AI agent testing whether a website lets agents complete a task.
Task: {task}
Rules:
- Stay on {origin}. Do not visit other websites.
- Do not enter personal data, create accounts, place orders or pay.
- When you know the answer, reply in text starting with "ANSWER:" and stop.
- If the website does not let you finish, reply "ANSWER: unable" and say why."""


@dataclass
class RunResult:
    answer: str | None = None
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    actions: list[str] = field(default_factory=list)


def _tokens(data: dict) -> tuple[int, int]:
    """Usage field names are not documented for this API; read the common shapes."""
    usage = data.get("usage") or data.get("usageMetadata") or {}
    if not isinstance(usage, dict):
        return 0, 0
    inputs = outputs = 0
    for key, value in usage.items():
        if not isinstance(value, int):
            continue
        name = key.lower()
        if "input" in name or "prompt" in name:
            inputs += value
        elif "output" in name or "candidates" in name:
            outputs += value
    return inputs, outputs


def _final_text(data: dict) -> str | None:
    texts = []
    for step in data.get("steps") or data.get("outputs") or []:
        if not isinstance(step, dict) or step.get("type") == "function_call":
            continue
        if isinstance(step.get("text"), str):
            texts.append(step["text"])
        for part in step.get("content") or []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])
    return "\n".join(texts).strip() or None


def _calls(data: dict) -> list[dict]:
    return [
        step
        for step in data.get("steps") or data.get("outputs") or []
        if isinstance(step, dict) and step.get("type") == "function_call"
    ]


def _point(args: dict, prefix: str = "") -> tuple[float, float]:
    x = float(args.get(prefix + "x", 500))
    y = float(args.get(prefix + "y", 500))
    return x / 1000 * VIEWPORT[0], y / 1000 * VIEWPORT[1]


async def _execute(page, navigate, origin: str, name: str, args: dict) -> str | None:
    """Run one UI action. Returns an error message for the model, or None."""
    mouse, keyboard = page.mouse, page.keyboard
    if name in ("click", "click_at", "double_click", "triple_click", "right_click", "middle_click"):
        x, y = _point(args)
        button = {"right_click": "right", "middle_click": "middle"}.get(name, "left")
        count = {"double_click": 2, "triple_click": 3}.get(name, 1)
        await mouse.click(x, y, button=button, click_count=count)
    elif name in ("move", "hover_at"):
        await mouse.move(*_point(args))
    elif name in ("mouse_down", "mouse_up"):
        await mouse.move(*_point(args))
        await (mouse.down() if name == "mouse_down" else mouse.up())
    elif name in ("type", "type_text_at"):
        if "x" in args and "y" in args:
            await mouse.click(*_point(args))
        await keyboard.type(str(args.get("text", ""))[:500])
        if args.get("press_enter"):
            await keyboard.press("Enter")
    elif name in ("scroll", "scroll_document", "scroll_at"):
        if "x" in args and "y" in args:
            await mouse.move(*_point(args))
        amount = int(args.get("magnitude_in_pixels") or args.get("magnitude") or 600)
        direction = str(args.get("direction", "down")).lower()
        dx = amount if direction == "right" else -amount if direction == "left" else 0
        dy = amount if direction == "down" else -amount if direction == "up" else 0
        await mouse.wheel(dx, dy)
    elif name in ("press_key", "key_down", "key_up"):
        key = str(args.get("key", ""))[:40]
        action = {"key_down": keyboard.down, "key_up": keyboard.up}.get(name, keyboard.press)
        await action(key)
    elif name in ("hotkey", "key_combination"):
        keys = args.get("keys")
        combo = "+".join(keys) if isinstance(keys, list) else str(keys or "")
        await keyboard.press(combo[:60])
    elif name == "drag_and_drop":
        await mouse.move(*_point(args, "start_"))
        await mouse.down()
        await mouse.move(*_point(args, "end_"))
        await mouse.up()
    elif name in ("wait", "wait_5_seconds"):
        await asyncio.sleep(min(float(args.get("seconds", 5)), 5))
    elif name == "navigate":
        target = urljoin(page.url, str(args.get("url", "")))
        if origin_of(target) != origin:
            return "Blocked: stay on the website under test."
        await navigate(target)
    elif name == "go_back":
        await page.go_back()
    elif name == "go_forward":
        await page.go_forward()
    elif name in ("take_screenshot", "open_web_browser"):
        pass
    else:
        return f"Unsupported action: {name}"
    return None


async def run_task(page, navigate, start_url: str, task: str, settings: Settings) -> RunResult:
    key = settings.gemini_api_key.get_secret_value()
    if not key:
        raise InferenceError("Configure GEMINI_API_KEY for Computer Use QA")
    origin = origin_of(start_url)
    result = RunResult()
    tools = [
        {
            "type": "computer_use",
            "environment": "browser",
            "enable_prompt_injection_detection": True,
        }
    ]
    deadline = time.monotonic() + settings.qa_task_timeout
    async with httpx.AsyncClient(
        timeout=60, trust_env=False, headers={"x-goog-api-key": key}
    ) as client:
        await navigate(start_url)
        shot = base64.b64encode(await page.screenshot(type="png")).decode()
        body: dict = {
            "model": settings.qa_model,
            "input": [
                {"type": "text", "text": INSTRUCTIONS.format(task=task, origin=origin)},
                {"type": "image", "data": shot, "mime_type": "image/png"},
            ],
            "tools": tools,
        }
        while result.steps < settings.qa_max_steps:
            if time.monotonic() > deadline:
                result.error = "Time limit reached"
                return result
            response = await client.post(ENDPOINT, json=body)
            if response.status_code != 200:
                raise InferenceError(f"Computer Use returned HTTP {response.status_code}")
            data = response.json()
            used_in, used_out = _tokens(data)
            result.input_tokens += used_in
            result.output_tokens += used_out
            calls = _calls(data)
            if not calls:
                result.answer = _final_text(data)
                return result
            outputs = []
            for call in calls:
                name = str(call.get("name", ""))
                args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
                decision = args.get("safety_decision") or call.get("safety_decision") or {}
                if (
                    isinstance(decision, dict)
                    and decision.get("decision") == "require_confirmation"
                ):
                    result.error = "The model asked for confirmation; QA never confirms"
                    return result
                result.steps += 1
                result.actions.append(name)
                try:
                    problem = await _execute(page, navigate, origin, name, args)
                except (PlaywrightError, ValueError, TimeoutError) as exc:
                    # A failed UI action is reported back to the model, not fatal.
                    problem = f"Action failed: {type(exc).__name__}"
                await asyncio.sleep(0.4)
                shot = base64.b64encode(await page.screenshot(type="png")).decode()
                outputs.append(
                    {
                        "type": "function_result",
                        "name": name,
                        "call_id": call.get("call_id") or call.get("id"),
                        "result": [
                            {
                                "type": "text",
                                "text": json.dumps({"url": page.url, "error": problem}),
                            },
                            {"type": "image", "data": shot, "mime_type": "image/png"},
                        ],
                    }
                )
            body = {
                "model": settings.qa_model,
                "previous_interaction_id": data.get("id"),
                "input": outputs,
                "tools": tools,
            }
    result.error = "Step limit reached"
    return result
