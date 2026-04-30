from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from uuid import uuid4

from openai import AsyncOpenAI

from app.config import Settings
from app.lottery import GAME_NAMES, generate_numbers
from app.models import ChatGenerateRequest, LotteryResult, ModelCandidate
from app.rules import extract_numbers_from_text, normalize_numbers

HistoryKey = str


@dataclass(frozen=True)
class LLMProvider:
    name: str
    base_url: str
    api_key: str
    model: str


class ChatService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._history: dict[HistoryKey, deque[dict[str, str]]] = defaultdict(
            lambda: deque(maxlen=settings.max_history_messages)
        )

    async def generate(
        self,
        request: ChatGenerateRequest,
        today_result: LotteryResult | None,
    ) -> tuple[str, str, list[str], bool, str, list[ModelCandidate], str | None]:
        session_id = request.session_id or uuid4().hex
        fallback_numbers = generate_numbers(request.game)
        providers = _load_providers(self.settings)

        if not providers:
            reply = _fallback_reply(fallback_numbers)
            return session_id, reply, fallback_numbers, False, "fallback", [], "未配置大模型，使用本地随机生成。"

        if len(providers) == 1:
            candidate = await self._call_candidate(providers[0], request, today_result, fallback_numbers, session_id)
            if candidate.error:
                reply = _fallback_reply(fallback_numbers)
                numbers = fallback_numbers
            else:
                reply = candidate.reply
                numbers = candidate.recommended_numbers
            self._save_history(session_id, request.message, reply)
            return session_id, reply, numbers, candidate.error is None, "single_model", [candidate], None

        candidates = await asyncio.gather(
            *[
                self._call_candidate(provider, request, today_result, fallback_numbers, session_id)
                for provider in providers
            ]
        )
        valid_candidates = [candidate for candidate in candidates if not candidate.error]
        if not valid_candidates:
            reply = _fallback_reply(fallback_numbers)
            reason = "多个模型都调用失败或返回号码不符合玩法规则，使用本地随机生成。"
            return session_id, reply, fallback_numbers, False, "multi_model_fallback", list(candidates), reason

        reply, numbers, reason = await self._judge_candidates(
            providers[0],
            request,
            today_result,
            valid_candidates,
            fallback_numbers,
        )
        self._save_history(session_id, request.message, reply)
        return session_id, reply, numbers, True, "multi_model_discussion", list(candidates), reason

    async def _call_candidate(
        self,
        provider: LLMProvider,
        request: ChatGenerateRequest,
        today_result: LotteryResult | None,
        fallback_numbers: list[str],
        key: HistoryKey,
    ) -> ModelCandidate:
        messages = self._build_generation_messages(request, today_result, fallback_numbers, key)
        try:
            content = await _chat(provider, messages, self.settings.llm_timeout_seconds, temperature=0.8)
        except Exception as exc:
            return ModelCandidate(provider=provider.name, model=provider.model, reply="", error=str(exc))

        numbers = extract_numbers_from_text(request.game, content)
        if not numbers:
            return ModelCandidate(
                provider=provider.name,
                model=provider.model,
                reply=content,
                recommended_numbers=[],
                error="模型返回的号码不符合该彩票玩法规则，已跳过该候选。",
            )

        return ModelCandidate(
            provider=provider.name,
            model=provider.model,
            reply=content,
            recommended_numbers=numbers,
        )

    async def _judge_candidates(
        self,
        judge: LLMProvider,
        request: ChatGenerateRequest,
        today_result: LotteryResult | None,
        candidates: list[ModelCandidate],
        fallback_numbers: list[str],
    ) -> tuple[str, list[str], str]:
        payload = {
            "game": request.game,
            "game_name": GAME_NAMES[request.game],
            "rules": _rules_prompt(request.game),
            "today_result": today_result.model_dump(mode="json") if today_result else None,
            "user_message": request.message,
            "candidates": [candidate.model_dump() for candidate in candidates],
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "你是彩票号码生成结果评审助手。比较多个模型给出的候选号码，"
                    "可以选择其中一组，也可以综合后重新生成一组。必须严格遵守玩法规则，"
                    "必须说明号码仅供娱乐参考，不能承诺中奖或暗示可预测开奖结果。"
                    "只返回 JSON，格式为："
                    "{\"final_numbers\":[\"01\"],\"reply\":\"...\",\"decision_reason\":\"...\"}"
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            content = await _chat(judge, messages, self.settings.llm_timeout_seconds, temperature=0.4)
            parsed = _parse_json_object(content)
            numbers = normalize_numbers(request.game, [str(item) for item in parsed.get("final_numbers", [])])
            if not numbers:
                numbers = extract_numbers_from_text(request.game, content)
            reply = str(parsed.get("reply") or "").strip()
            reason = str(parsed.get("decision_reason") or "").strip()
            if numbers and reply:
                return reply, numbers, reason or "多模型评审后生成最终号码。"
        except Exception:
            pass

        best = candidates[0]
        reason = f"评审模型未返回有效号码，默认采用 {best.provider}/{best.model} 的合规候选号码。"
        return best.reply, best.recommended_numbers or fallback_numbers, reason

    def _build_generation_messages(
        self,
        request: ChatGenerateRequest,
        today_result: LotteryResult | None,
        fallback_numbers: list[str],
        key: HistoryKey,
    ) -> list[dict[str, str]]:
        user_context = {
            "game": request.game,
            "game_name": GAME_NAMES[request.game],
            "rules": _rules_prompt(request.game),
            "today_result": today_result.model_dump(mode="json") if today_result else None,
            "fallback_numbers_if_needed": fallback_numbers,
            "user_message": request.message,
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是彩票号码生成助手。必须严格按玩法规则输出一组号码。"
                    "不要输出多组候选，不要承诺中奖，不要暗示可以预测开奖结果。"
                    "输出要简洁，包含推荐号码和一句理由。"
                ),
            },
            *list(self._history[key]),
            {"role": "user", "content": json.dumps(user_context, ensure_ascii=False)},
        ]

    def _save_history(self, session_id: str, user_message: str, reply: str) -> None:
        self._history[session_id].append({"role": "user", "content": user_message})
        self._history[session_id].append({"role": "assistant", "content": reply})


async def _chat(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    timeout: float,
    temperature: float,
) -> str:
    client = AsyncOpenAI(api_key=provider.api_key, base_url=provider.base_url, timeout=timeout)
    completion = await client.chat.completions.create(
        model=provider.model,
        messages=messages,
        temperature=temperature,
    )
    return completion.choices[0].message.content or ""


def _load_providers(settings: Settings) -> list[LLMProvider]:
    if settings.llm_providers.strip():
        raw = json.loads(settings.llm_providers)
        providers = raw if isinstance(raw, list) else [raw]
        return [
            LLMProvider(
                name=str(item.get("name") or item.get("model") or f"provider_{index + 1}"),
                base_url=str(item["base_url"]),
                api_key=str(item["api_key"]),
                model=str(item["model"]),
            )
            for index, item in enumerate(providers)
            if item.get("base_url") and item.get("api_key") and item.get("model")
        ]

    if settings.llm_base_url and settings.llm_api_key and settings.llm_model:
        return [
            LLMProvider(
                name=settings.llm_provider_name,
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
            )
        ]
    return []


def _fallback_reply(numbers: list[str]) -> str:
    return (
        f"推荐号码：{' '.join(numbers)}。\n"
        "说明：当前没有可用的大模型合规结果，已使用本地规则生成；号码仅供娱乐参考。"
    )


def _rules_prompt(game: str) -> str:
    prompts = {
        "ssq": "双色球：6 个红球，范围 01-33，不重复；1 个蓝球，范围 01-16。格式：01 02 03 04 05 06 +07。",
        "dlt": "超级大乐透：5 个前区号码，范围 01-35，不重复；2 个后区号码，范围 01-12，不重复。格式：01 02 03 04 05 +06 +07。",
        "fc3d": "福彩3D：3 位数字，每位范围 0-9，可以重复。格式：1 2 3。",
        "pl3": "排列三：3 位数字，每位范围 0-9，可以重复。格式：1 2 3。",
        "pl5": "排列五：5 位数字，每位范围 0-9，可以重复。格式：1 2 3 4 5。",
    }
    return prompts.get(game, "")


def _parse_json_object(text: str) -> dict[str, object]:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("No JSON object found")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("JSON payload is not an object")
    return parsed
