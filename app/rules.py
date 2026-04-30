from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import LotteryGame


@dataclass(frozen=True)
class AreaRule:
    count: int
    min_value: int
    max_value: int
    prefix: str = ""
    unique: bool = True


LOTTERY_RULES: dict[LotteryGame, tuple[AreaRule, ...]] = {
    "ssq": (AreaRule(6, 1, 33), AreaRule(1, 1, 16, prefix="+")),
    "dlt": (AreaRule(5, 1, 35), AreaRule(2, 1, 12, prefix="+")),
    "fc3d": (AreaRule(3, 0, 9, unique=False),),
    "pl3": (AreaRule(3, 0, 9, unique=False),),
    "pl5": (AreaRule(5, 0, 9, unique=False),),
}


def normalize_numbers(game: LotteryGame, numbers: list[str]) -> list[str]:
    if game in {"ssq", "dlt"}:
        blue_count = 1 if game == "ssq" else 2
        front, back = _split_area_input(numbers, blue_count)
        front_rule, back_rule = LOTTERY_RULES[game]
        front_norm = _normalize_area(front, front_rule)
        back_norm = _normalize_area(back, back_rule)
        if len(front_norm) != front_rule.count or len(back_norm) != back_rule.count:
            return []
        return [*front_norm, *back_norm]

    rule = LOTTERY_RULES[game][0]
    digits = _normalize_area(_digits_input(numbers), rule)
    return digits if len(digits) == rule.count else []


def extract_numbers_from_text(game: LotteryGame, text: str) -> list[str]:
    text = _focus_recommendation_segment(text)
    if game in {"ssq", "dlt"}:
        blue_count = 1 if game == "ssq" else 2
        front_raw, back_raw = _extract_double_area_text(text, blue_count)
        return normalize_numbers(game, [*front_raw, *(f"+{item}" for item in back_raw)])

    digits = re.findall(r"\d", text)
    return normalize_numbers(game, digits)


def ensure_valid_numbers(game: LotteryGame, numbers: list[str]) -> bool:
    return bool(normalize_numbers(game, numbers))


def _split_area_input(numbers: list[str], back_count: int) -> tuple[list[str], list[str]]:
    front: list[str] = []
    back: list[str] = []
    for raw in numbers:
        token = str(raw).strip().strip("`'\"")
        if token.startswith("+"):
            back.append(token[1:])
        else:
            front.append(token)
    if not back and len(front) > back_count:
        back = front[-back_count:]
        front = front[:-back_count]
    return front, back


def _extract_double_area_text(text: str, back_count: int) -> tuple[list[str], list[str]]:
    normalized = (
        text.replace("＋", "+")
        .replace("，", " ")
        .replace(",", " ")
        .replace("、", " ")
        .replace("；", " ")
        .replace(";", " ")
        .replace("`", " ")
    )
    if "+" in normalized:
        before, after = normalized.split("+", 1)
        return re.findall(r"\d{1,2}", before), re.findall(r"\d{1,2}", after)

    tokens = re.findall(r"\d{1,2}", normalized)
    if len(tokens) > back_count:
        return tokens[:-back_count], tokens[-back_count:]
    return tokens, []


def _digits_input(numbers: list[str]) -> list[str]:
    if len(numbers) == 1 and str(numbers[0]).isdigit() and len(str(numbers[0])) > 1:
        return list(str(numbers[0]))
    return [str(item).strip().lstrip("+") for item in numbers]


def _normalize_area(numbers: list[str], rule: AreaRule) -> list[str]:
    picked: list[int] = []
    seen: set[int] = set()
    for raw in numbers:
        token = str(raw).strip()
        if not token.isdigit():
            continue
        value = int(token)
        if value < rule.min_value or value > rule.max_value:
            continue
        if rule.unique and value in seen:
            continue
        picked.append(value)
        seen.add(value)
        if len(picked) == rule.count:
            break
    width = 1 if rule.max_value <= 9 else 2
    return [f"{rule.prefix}{value:0{width}d}" for value in sorted(picked)]


def _focus_recommendation_segment(text: str) -> str:
    markers = ["推荐号码", "最终号码", "号码：", "号码:"]
    for marker in markers:
        index = text.rfind(marker)
        if index >= 0:
            segment = text[index + len(marker) :]
            return segment.split("\n", 1)[0] or segment
    return text
