from __future__ import annotations

import json
import secrets
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from app.config import Settings
from app.models import LotteryGame, LotteryResult


GAME_NAMES: dict[LotteryGame, str] = {
    "ssq": "双色球",
    "dlt": "大乐透",
    "fc3d": "福彩3D",
    "pl3": "排列三",
    "pl5": "排列五",
}


def generate_numbers(game: LotteryGame) -> list[str]:
    if game == "ssq":
        red = sorted(_sample_range(1, 33, 6))
        blue = _sample_range(1, 16, 1)
        return [*(f"{n:02d}" for n in red), f"+{blue[0]:02d}"]
    if game == "dlt":
        front = sorted(_sample_range(1, 35, 5))
        back = sorted(_sample_range(1, 12, 2))
        return [*(f"{n:02d}" for n in front), *(f"+{n:02d}" for n in back)]
    if game in {"fc3d", "pl3"}:
        return [str(secrets.randbelow(10)) for _ in range(3)]
    if game == "pl5":
        return [str(secrets.randbelow(10)) for _ in range(5)]
    raise ValueError(f"Unsupported game: {game}")


async def get_today_result(settings: Settings, game: LotteryGame) -> LotteryResult:
    return await get_result_by_date(settings, game, date.today())


async def get_result_by_date(settings: Settings, game: LotteryGame, draw_date: date) -> LotteryResult:
    remote = await _fetch_remote_result(settings, game, draw_date)
    if remote:
        return remote

    local = _fetch_local_result(settings, game, draw_date)
    if local:
        return local

    if settings.lottery_auto_fetch:
        official = await _fetch_official_result(settings, game, draw_date)
        if official:
            return official

    return LotteryResult(
        game=game,
        draw_date=draw_date,
        numbers=[],
        source="not_configured",
        raw={
            "message": "No result found. Configure LOTTERY_API_URL or update data/lottery_results.json.",
        },
    )


async def _fetch_remote_result(settings: Settings, game: LotteryGame, draw_date: date) -> LotteryResult | None:
    if not settings.lottery_api_url:
        return None

    headers = {}
    if settings.lottery_api_key:
        headers["Authorization"] = f"Bearer {settings.lottery_api_key}"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            settings.lottery_api_url,
            params={"game": game, "date": draw_date.isoformat()},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    return _payload_to_result(payload, game, draw_date, "remote_api")


async def _fetch_official_result(settings: Settings, game: LotteryGame, draw_date: date) -> LotteryResult | None:
    if game in {"ssq", "fc3d"}:
        return await _fetch_cwl_result(settings, game, draw_date)
    if game in {"dlt", "pl3", "pl5"}:
        return await _fetch_sporttery_result(settings, game, draw_date)
    return None


async def _fetch_cwl_result(settings: Settings, game: LotteryGame, draw_date: date) -> LotteryResult | None:
    names = {"ssq": "ssq", "fc3d": "3d"}
    url = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
    params = {"name": names[game], "issueCount": "10"}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=_browser_headers())
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None

    records = payload.get("result") or payload.get("data") or []
    return _pick_record(records, game, draw_date, settings.lottery_latest_if_date_missing, "official_cwl")


async def _fetch_sporttery_result(settings: Settings, game: LotteryGame, draw_date: date) -> LotteryResult | None:
    game_no = {"dlt": "85", "pl3": "35", "pl5": "350133"}
    url = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
    params = {
        "gameNo": game_no[game],
        "provinceId": "0",
        "pageSize": "10",
        "isVerify": "1",
        "pageNo": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=_browser_headers())
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None

    value = payload.get("value") or {}
    records = value.get("list") or payload.get("data") or []
    return _pick_record(records, game, draw_date, settings.lottery_latest_if_date_missing, "official_sporttery")


def _fetch_local_result(settings: Settings, game: LotteryGame, draw_date: date) -> LotteryResult | None:
    path = Path(settings.lottery_data_file)
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get(game, [])
    for record in records:
        if str(record.get("draw_date")) == draw_date.isoformat():
            return _payload_to_result(record, game, draw_date, "local_file")
    return None


def _pick_record(
    records: list[dict[str, Any]],
    game: LotteryGame,
    draw_date: date,
    latest_if_missing: bool,
    source: str,
) -> LotteryResult | None:
    parsed = [_payload_to_result(record, game, draw_date, source) for record in records if isinstance(record, dict)]
    for result in parsed:
        if result.draw_date == draw_date:
            return result
    if latest_if_missing and parsed:
        latest = sorted(parsed, key=lambda item: item.draw_date, reverse=True)[0]
        latest.source = f"{source}_latest"
        return latest
    return None


def _payload_to_result(payload: dict[str, Any], game: LotteryGame, draw_date: date, source: str) -> LotteryResult:
    numbers = payload.get("numbers")
    if numbers is None:
        result = payload.get("lotteryDrawResult") or payload.get("drawResult")
        if isinstance(result, str) and result:
            numbers = result.replace("+", " ").replace(",", " ").split()
        else:
            red = _as_list(payload.get("red") or payload.get("front") or payload.get("redNum"))
            blue = _as_list(payload.get("blue") or payload.get("back") or payload.get("blueNum"))
            numbers = [*red, *(f"+{n}" for n in blue)]

    raw_date = (
        payload.get("draw_date")
        or payload.get("date")
        or payload.get("lotteryDrawTime")
        or payload.get("openTime")
        or draw_date
    )
    parsed_date = date.fromisoformat(str(raw_date)[:10])
    return LotteryResult(
        game=game,
        draw_date=parsed_date,
        issue=payload.get("issue") or payload.get("draw_no") or payload.get("code") or payload.get("lotteryDrawNum"),
        numbers=[str(item) for item in numbers],
        source=source,
        raw=payload,
    )


def _sample_range(start: int, end: int, count: int) -> list[int]:
    pool = list(range(start, end + 1))
    picked: list[int] = []
    for _ in range(count):
        index = secrets.randbelow(len(pool))
        picked.append(pool.pop(index))
    return picked


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [item for item in value.replace("+", ",").replace(" ", ",").split(",") if item]
    return [str(value)]


def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.baidu.com/",
    }
