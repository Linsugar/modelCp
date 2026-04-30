from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models import LotteryCheckRequest, LotteryCheckResponse, LotteryResult


@dataclass(frozen=True)
class PrizeDecision:
    level: str | None
    amount: float | None
    amount_source: str
    matched: dict[str, int | list[str]]
    message: str


BUILT_IN_AMOUNTS: dict[str, dict[str, float]] = {
    "ssq": {
        "三等奖": 3000,
        "四等奖": 200,
        "五等奖": 10,
        "六等奖": 5,
    },
    "dlt": {
        "四等奖": 3000,
        "五等奖": 300,
        "六等奖": 200,
        "七等奖": 100,
        "八等奖": 15,
        "九等奖": 5,
    },
    "fc3d": {
        "直选": 1040,
        "组三": 346,
        "组六": 173,
    },
    "pl3": {
        "直选": 1040,
        "组三": 346,
        "组六": 173,
    },
    "pl5": {
        "一等奖": 100000,
    },
}

PRIZE_LEVEL_ALIASES: dict[str, list[str]] = {
    "一等奖": ["level_1", "first", "1"],
    "二等奖": ["level_2", "second", "2"],
    "三等奖": ["level_3", "third", "3"],
    "四等奖": ["level_4", "fourth", "4"],
    "五等奖": ["level_5", "fifth", "5"],
    "六等奖": ["level_6", "sixth", "6"],
    "七等奖": ["level_7", "seventh", "7"],
    "八等奖": ["level_8", "eighth", "8"],
    "九等奖": ["level_9", "ninth", "9"],
    "直选": ["direct"],
    "组三": ["group_3"],
    "组六": ["group_6"],
}


def check_ticket(request: LotteryCheckRequest, draw_result: LotteryResult) -> LotteryCheckResponse:
    if not draw_result.numbers:
        draw_date = request.draw_date or request.generated_at.date()
        return LotteryCheckResponse(
            game=request.game,
            generated_at=request.generated_at,
            draw_date=draw_date,
            checked_numbers=request.numbers,
            draw_numbers=[],
            is_winning=False,
            amount_source="none",
            message="未找到对应日期的开奖数据，无法判断是否中奖。",
            draw_result=draw_result,
        )

    if request.game == "ssq":
        decision = _check_ssq(request.numbers, draw_result)
    elif request.game == "dlt":
        decision = _check_dlt(request.numbers, draw_result)
    elif request.game in {"fc3d", "pl3"}:
        decision = _check_3d(request.game, request.numbers, draw_result)
    elif request.game == "pl5":
        decision = _check_pl5(request.numbers, draw_result)
    else:
        decision = PrizeDecision(None, None, "none", {}, "暂不支持该彩票类型。")

    return LotteryCheckResponse(
        game=request.game,
        generated_at=request.generated_at,
        draw_date=draw_result.draw_date,
        checked_numbers=request.numbers,
        draw_numbers=draw_result.numbers,
        is_winning=decision.level is not None,
        prize_level=decision.level,
        prize_amount=decision.amount,
        amount_source=decision.amount_source,
        matched=decision.matched,
        message=decision.message,
        draw_result=draw_result,
    )


def _check_ssq(numbers: list[str], draw_result: LotteryResult) -> PrizeDecision:
    user_red, user_blue = _split_area_numbers(numbers, blue_count=1)
    draw_red, draw_blue = _split_area_numbers(draw_result.numbers, blue_count=1)
    red_hits = sorted(set(user_red) & set(draw_red))
    blue_hits = sorted(set(user_blue) & set(draw_blue))
    red_count = len(red_hits)
    blue_count = len(blue_hits)

    level: str | None = None
    if red_count == 6 and blue_count == 1:
        level = "一等奖"
    elif red_count == 6:
        level = "二等奖"
    elif red_count == 5 and blue_count == 1:
        level = "三等奖"
    elif red_count == 5 or (red_count == 4 and blue_count == 1):
        level = "四等奖"
    elif red_count == 4 or (red_count == 3 and blue_count == 1):
        level = "五等奖"
    elif blue_count == 1:
        level = "六等奖"

    matched = {
        "red_count": red_count,
        "blue_count": blue_count,
        "red_numbers": red_hits,
        "blue_numbers": blue_hits,
    }
    return _decision("ssq", level, draw_result, matched)


def _check_dlt(numbers: list[str], draw_result: LotteryResult) -> PrizeDecision:
    user_front, user_back = _split_area_numbers(numbers, blue_count=2)
    draw_front, draw_back = _split_area_numbers(draw_result.numbers, blue_count=2)
    front_hits = sorted(set(user_front) & set(draw_front))
    back_hits = sorted(set(user_back) & set(draw_back))
    front_count = len(front_hits)
    back_count = len(back_hits)

    level: str | None = None
    if front_count == 5 and back_count == 2:
        level = "一等奖"
    elif front_count == 5 and back_count == 1:
        level = "二等奖"
    elif front_count == 5 or (front_count == 4 and back_count == 2):
        level = "三等奖"
    elif (front_count == 4 and back_count == 1) or (front_count == 3 and back_count == 2):
        level = "四等奖"
    elif front_count == 4 or (front_count == 3 and back_count == 1) or (front_count == 2 and back_count == 2):
        level = "五等奖"
    elif (front_count == 3) or (front_count == 1 and back_count == 2) or (front_count == 2 and back_count == 1):
        level = "六等奖"
    elif (front_count == 2) or (front_count == 0 and back_count == 2) or (front_count == 1 and back_count == 1):
        level = "七等奖"
    elif front_count == 1 or back_count == 2:
        level = "八等奖"
    elif back_count == 1:
        level = "九等奖"

    matched = {
        "front_count": front_count,
        "back_count": back_count,
        "front_numbers": front_hits,
        "back_numbers": back_hits,
    }
    return _decision("dlt", level, draw_result, matched)


def _check_3d(game: str, numbers: list[str], draw_result: LotteryResult) -> PrizeDecision:
    user_digits = _digits(numbers)
    draw_digits = _digits(draw_result.numbers)
    matched = {
        "position_count": sum(1 for a, b in zip(user_digits, draw_digits) if a == b),
        "numbers": [a for a, b in zip(user_digits, draw_digits) if a == b],
    }
    if len(user_digits) != 3 or len(draw_digits) != 3:
        return PrizeDecision(None, None, "none", matched, "号码格式不完整，无法判断。")

    level = None
    if user_digits == draw_digits:
        level = "直选"
    elif sorted(user_digits) == sorted(draw_digits):
        unique_count = len(set(draw_digits))
        level = "组三" if unique_count == 2 else "组六"
    return _decision(game, level, draw_result, matched)


def _check_pl5(numbers: list[str], draw_result: LotteryResult) -> PrizeDecision:
    user_digits = _digits(numbers)
    draw_digits = _digits(draw_result.numbers)
    matched = {
        "position_count": sum(1 for a, b in zip(user_digits, draw_digits) if a == b),
        "numbers": [a for a, b in zip(user_digits, draw_digits) if a == b],
    }
    level = "一等奖" if len(user_digits) == 5 and user_digits == draw_digits else None
    return _decision("pl5", level, draw_result, matched)


def _decision(
    game: str,
    level: str | None,
    draw_result: LotteryResult,
    matched: dict[str, int | list[str]],
) -> PrizeDecision:
    if level is None:
        return PrizeDecision(None, None, "none", matched, "未中奖。")

    amount, source = _resolve_amount(game, level, draw_result.raw)
    if amount is None:
        return PrizeDecision(level, None, source, matched, f"中奖，奖级：{level}；奖金需要开奖数据提供。")
    return PrizeDecision(level, amount, source, matched, f"中奖，奖级：{level}，奖金：{amount:g} 元。")


def _resolve_amount(game: str, level: str, raw: dict[str, Any] | None) -> tuple[float | None, str]:
    raw_table = (raw or {}).get("prize_table") or (raw or {}).get("prizes") or {}
    raw_amount = None
    if isinstance(raw_table, dict):
        for key in [level, *PRIZE_LEVEL_ALIASES.get(level, [])]:
            raw_amount = raw_table.get(key)
            if raw_amount not in (None, ""):
                break
    if isinstance(raw_amount, dict):
        raw_amount = raw_amount.get("amount") or raw_amount.get("money")
    if raw_amount not in (None, ""):
        try:
            return float(raw_amount), "draw_data"
        except (TypeError, ValueError):
            pass

    built_in = BUILT_IN_AMOUNTS.get(game, {}).get(level)
    if built_in is not None:
        return built_in, "built_in"
    return None, "unknown"


def _split_area_numbers(numbers: list[str], blue_count: int) -> tuple[list[str], list[str]]:
    front: list[str] = []
    back: list[str] = []
    for item in numbers:
        token = str(item).strip()
        if token.startswith("+"):
            back.append(_normalize_number(token[1:]))
        else:
            front.append(_normalize_number(token))

    if not back and len(front) > blue_count:
        back = front[-blue_count:]
        front = front[:-blue_count]
    return front, back


def _digits(numbers: list[str]) -> list[str]:
    if len(numbers) == 1 and str(numbers[0]).isdigit() and len(str(numbers[0])) > 1:
        return list(str(numbers[0]))
    return [str(item).strip().lstrip("+") for item in numbers]


def _normalize_number(value: str) -> str:
    value = value.strip()
    if value.isdigit():
        return value.zfill(2)
    return value
