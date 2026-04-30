from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


LotteryGame = Literal["ssq", "dlt", "fc3d", "pl3", "pl5"]


class HealthResponse(BaseModel):
    status: str
    app: str


class LotteryResult(BaseModel):
    game: LotteryGame
    draw_date: date
    issue: str | None = None
    numbers: list[str] = Field(default_factory=list)
    source: str
    raw: dict[str, Any] | None = None


class ChatGenerateRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=120)
    game: LotteryGame = "ssq"
    message: str = Field(..., min_length=1, max_length=2000)
    include_today_result: bool = True


class ModelCandidate(BaseModel):
    provider: str
    model: str
    reply: str
    recommended_numbers: list[str] = Field(default_factory=list)
    error: str | None = None


class ChatGenerateResponse(BaseModel):
    session_id: str
    game: LotteryGame
    reply: str
    recommended_numbers: list[str] = Field(default_factory=list)
    llm_used: bool
    generation_mode: str = "fallback"
    candidates: list[ModelCandidate] = Field(default_factory=list)
    decision_reason: str | None = None
    today_result: LotteryResult | None = None


class LotteryCheckRequest(BaseModel):
    game: LotteryGame = "ssq"
    numbers: list[str] = Field(..., min_length=1)
    generated_at: datetime
    draw_date: date | None = None


class LotteryCheckResponse(BaseModel):
    game: LotteryGame
    generated_at: datetime
    draw_date: date
    checked_numbers: list[str]
    draw_numbers: list[str] = Field(default_factory=list)
    is_winning: bool
    prize_level: str | None = None
    prize_amount: float | None = None
    currency: str = "CNY"
    amount_source: str
    matched: dict[str, int | list[str]] = Field(default_factory=dict)
    message: str
    draw_result: LotteryResult | None = None
