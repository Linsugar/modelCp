import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.llm import ChatService
from app.models import (
    ChatGenerateRequest,
    ChatGenerateResponse,
    HealthResponse,
    LotteryCheckRequest,
    LotteryCheckResponse,
    LotteryGame,
    LotteryResult,
)
from app.lottery import get_recent_results, get_result_by_date, get_today_result
from app.prize import check_ticket
from app.security import require_client_api_key

app = FastAPI(title="Lottery LLM API", version="0.1.0")
_chat_service: ChatService | None = None
logger = logging.getLogger("lottery_api.requests")
logging.getLogger("uvicorn.access").disabled = True

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request_with_time(request, call_next):
    started = time.perf_counter()
    request_time = datetime.now(ZoneInfo(settings.log_timezone)).strftime("%Y-%m-%d %H:%M:%S")
    client_host = request.client.host if request.client else "-"
    method = request.method
    path = request.url.path
    if request.url.query:
        path = f"{path}?{request.url.query}"

    # 读取请求体
    body_bytes = await request.body()
    request_body = body_bytes.decode("utf-8", errors="replace")[:2000] if body_bytes else ""

    print(
        f"{request_time} {client_host} {method} {path}",
        flush=True,
    )
    if request_body:
        print(f"  -> request: {request_body}", flush=True)

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(f"  <- 500 {elapsed_ms:.2f}ms", flush=True)
        logger.exception("Unhandled request error")
        raise

    # 读取响应体
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk
    response_text = response_body.decode("utf-8", errors="replace")[:2000]

    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"  <- {response.status_code} {elapsed_ms:.2f}ms", flush=True)
    if response_text:
        print(f"  <- response: {response_text}", flush=True)

    return Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


def get_chat_service(settings: Settings = Depends(get_settings)) -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService(settings)
    return _chat_service


@app.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@app.get(
    "/api/v1/lottery/today",
    response_model=LotteryResult,
    dependencies=[Depends(require_client_api_key)],
)
async def lottery_today(
    game: LotteryGame = "ssq",
    settings: Settings = Depends(get_settings),
) -> LotteryResult:
    return await get_today_result(settings, game)


@app.post(
    "/api/v1/chat/generate",
    response_model=ChatGenerateResponse,
    dependencies=[Depends(require_client_api_key)],
)
async def chat_generate(
    request: ChatGenerateRequest,
    settings: Settings = Depends(get_settings),
    service: ChatService = Depends(get_chat_service),
) -> ChatGenerateResponse:
    today_result = await get_today_result(settings, request.game) if request.include_today_result else None
    recent_results = await get_recent_results(settings, request.game, settings.lottery_history_count)
    session_id, reply, numbers, llm_used, generation_mode, candidates, decision_reason = await service.generate(
        request,
        today_result,
        recent_results,
    )
    return ChatGenerateResponse(
        session_id=session_id,
        game=request.game,
        reply=reply,
        recommended_numbers=numbers,
        llm_used=llm_used,
        generation_mode=generation_mode,
        candidates=candidates,
        decision_reason=decision_reason,
        today_result=today_result,
    )


@app.post(
    "/api/v1/lottery/check",
    response_model=LotteryCheckResponse,
    dependencies=[Depends(require_client_api_key)],
)
async def lottery_check(
    request: LotteryCheckRequest,
    settings: Settings = Depends(get_settings),
) -> LotteryCheckResponse:
    draw_date = request.draw_date or request.generated_at.date()
    draw_result = await get_result_by_date(settings, request.game, draw_date)
    return check_ticket(request, draw_result)
