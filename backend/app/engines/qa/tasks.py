"""QA task suites with rule-based verification of the agent's final answer.

A run passes only when the answer matches the site's known facts. A claim of success
without the right answer fails. Suites are read-only: no orders, payments or accounts.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class QATask:
    key: str
    prompt: str
    verify: Callable[[str], bool]


def _answer(text: str | None) -> str:
    """The text after ANSWER:, lowercased, with currency symbols and separators removed."""
    value = text or ""
    if "answer:" in value.lower():
        value = value[value.lower().rindex("answer:") + 7 :]
    return value.lower().replace("₹", " ").replace(",", "").replace("rs.", " ")


def _numbers(text: str) -> set[float]:
    return {float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)}


def has_number(value: float) -> Callable[[str], bool]:
    return lambda text: value in _numbers(_answer(text))


def has_words(*words: str) -> Callable[[str], bool]:
    return lambda text: all(word in _answer(text) for word in words)


def yes_no(expected: bool) -> Callable[[str], bool]:
    def check(text: str) -> bool:
        answer = _answer(text)
        said_yes = re.search(r"\byes\b", answer) is not None
        said_no = re.search(r"\bno\b|\bnot\b|out of stock|unavailable", answer) is not None
        return said_yes and not said_no if expected else said_no and not said_yes

    return check


def exact_sizes(expected: set[int]) -> Callable[[str], bool]:
    return lambda text: {int(n) for n in _numbers(_answer(text)) if n.is_integer()} == expected


# Fictional demo store (demo-store/catalog.json). Facts are fixed so runs are repeatable.
DEMO_STORE = [
    QATask("trail_runner_price", "What is the price of the Trail Runner shoe?", has_number(2799)),
    QATask(
        "cheapest_product",
        "Which product in the store is the cheapest, and what does it cost?",
        lambda t: has_words("easy slide")(t) and has_number(899)(t),
    ),
    QATask(
        "size9_running_under_3000",
        "Which running shoe under ₹3,000 is in stock in UK size 9? Give its name.",
        has_words("trail runner"),
    ),
    QATask(
        "city_walker_sizes",
        "Which UK sizes of the City Walker are in stock? List only the sizes.",
        exact_sizes({7, 8, 10, 11}),
    ),
    QATask(
        "aero_racer_size11",
        "Is the Aero Racer available in UK size 11? Answer yes or no.",
        yes_no(True),
    ),
    QATask(
        "studio_flex_size9",
        "Is the Studio Flex in stock in UK size 9? Answer yes or no.",
        yes_no(False),
    ),
    QATask("hiking_boot_price", "How much does the hiking boot cost?", has_number(4599)),
    QATask(
        "returns_window",
        "How many days do customers have to return unworn shoes?",
        has_number(30),
    ),
    QATask(
        "free_delivery_threshold",
        "Above what order value is delivery free?",
        has_number(1500),
    ),
    QATask(
        "delivery_estimate",
        "How long does delivery take to PIN code 560001?",
        lambda t: has_number(2)(t) and has_number(3)(t),
    ),
]

SUITES = {"demo-store": DEMO_STORE}
