"""ArogyaAI FastAPI application - API plus the static single-page frontend."""

from __future__ import annotations

import base64
import binascii
import hmac
import json
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import store
from .config import WEB_DIR, get_settings
from .hospitals import CATEGORIES, HospitalLookupError, find_nearby
from .llm import LLMError, build_user_content, stream_chat
from .prompts import LANGUAGES, build_system_prompt, normalise_language
from .safety import HELPLINES, detect_emergency, detect_escalation

# GenAI Generated code - Start

settings = get_settings()

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<payload>.+)$", re.S)

#: ip -> timestamps of recent requests (simple in-process throttle)
_hits: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    store.init(settings.db_path)
    yield


app = FastAPI(
    title="ArogyaAI",
    version="1.0.0",
    description="Home remedies, nutrition and preventive health guidance in Indian languages.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request) -> None:
    limit = settings.rate_limit_per_min
    if limit <= 0:
        return
    now = time.time()
    bucket = _hits[_client_ip(request)]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute before trying again.",
        )
    bucket.append(now)


def _require_access(request: Request) -> None:
    """Shared-passcode gate for endpoints that cost money or hold user data.

    This is deliberately not a login system - it is a single secret that keeps a
    public URL from burning your model quota. ``/healthz``, ``/api/config`` and
    ``/api/helplines`` stay open so emergency numbers are always reachable.
    """
    if not settings.access_code:
        return
    provided = request.headers.get("x-access-code", "")
    if not hmac.compare_digest(provided, settings.access_code):
        raise HTTPException(status_code=401, detail="Invalid or missing access code.")


def _validate_image(data_url: str) -> str:
    match = _DATA_URL_RE.match(data_url.strip())
    if not match:
        raise HTTPException(
            status_code=400, detail="Image must be a base64 data URL."
        )
    mime = match.group("mime").lower()
    if mime not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG or WebP images are supported.",
        )
    payload = match.group("payload")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Image data is not valid base64.") from exc
    if len(raw) > settings.max_image_bytes:
        limit_mb = settings.max_image_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Image is larger than {limit_mb:.1f} MB. Please send a smaller photo.",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="Image data is empty.")
    return data_url.strip()


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _clean_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r"[^\w\s.'-]", "", name).strip()[:60]
    return cleaned or None


# --------------------------------------------------------------------------- #
# schemas
# --------------------------------------------------------------------------- #
class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=8000)
    language: str = Field(default="en", max_length=12)
    session_id: str | None = Field(default=None, max_length=64)
    user_name: str | None = Field(default=None, max_length=80)
    image: str | None = None


class SessionRequest(BaseModel):
    language: str = Field(default="en", max_length=12)
    user_name: str | None = Field(default=None, max_length=80)


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"status": "ok", "model_configured": settings.configured}


@app.get("/api/config")
async def api_config() -> dict[str, Any]:
    """Public, secret-free config consumed by the frontend on load."""
    return {
        "app_name": "ArogyaAI",
        "model_label": settings.display_model,
        "vision_enabled": bool(settings.vision_model),
        "model_configured": settings.configured,
        "requires_code": bool(settings.access_code),
        "languages": [
            {"code": code, **meta} for code, meta in LANGUAGES.items()
        ],
        "hospital_categories": list(CATEGORIES),
        "max_image_bytes": settings.max_image_bytes,
    }


@app.get("/api/helplines")
async def api_helplines() -> dict[str, Any]:
    return {"helplines": HELPLINES}


@app.post("/api/session")
async def api_create_session(
    payload: SessionRequest, request: Request
) -> dict[str, str]:
    _require_access(request)
    session_id = store.create_session(
        _clean_name(payload.user_name), normalise_language(payload.language)
    )
    return {"session_id": session_id}


@app.get("/api/history/{session_id}")
async def api_history(session_id: str, request: Request) -> dict[str, Any]:
    _require_access(request)
    return {"session_id": session_id, "messages": store.session_history(session_id)}


@app.delete("/api/history/{session_id}")
async def api_clear_history(session_id: str, request: Request) -> dict[str, bool]:
    _require_access(request)
    store.delete_session(session_id)
    return {"deleted": True}


@app.get("/api/hospitals")
async def api_hospitals(
    request: Request,
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, ge=0.5, le=25.0),
    category: str = Query("all"),
    limit: int = Query(25, ge=1, le=60),
) -> dict[str, Any]:
    _require_access(request)
    try:
        return await find_nearby(
            lat,
            lon,
            settings=settings,
            radius_km=radius_km,
            category=category,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HospitalLookupError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/chat")
async def api_chat(payload: ChatRequest, request: Request) -> StreamingResponse:
    _require_access(request)
    _rate_limit(request)

    text = (payload.message or "").strip()[: settings.max_message_chars]
    image = _validate_image(payload.image) if payload.image else None
    if not text and not image:
        raise HTTPException(status_code=400, detail="Send a message or an image.")

    language = normalise_language(payload.language)
    user_name = _clean_name(payload.user_name)
    session_id = store.ensure_session(payload.session_id, user_name, language)

    emergency = detect_emergency(text, language)
    escalation = detect_escalation(text)

    history = store.recent_messages(session_id, settings.history_turns)
    store.add_message(session_id, "user", text or "[photo]", has_image=bool(image))

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": build_system_prompt(
                language,
                user_name=user_name,
                has_image=bool(image),
                escalation=escalation,
            ),
        }
    ]
    for item in history:
        if item["role"] in ("user", "assistant") and item["content"]:
            messages.append({"role": item["role"], "content": item["content"]})
    messages.append(
        {
            "role": "user",
            "content": build_user_content(
                text or "Please look at this photo and tell me what you observe.",
                image,
            ),
        }
    )

    model = settings.vision_model if image else settings.text_model

    async def generator() -> AsyncIterator[str]:
        yield _sse(
            {
                "type": "meta",
                "session_id": session_id,
                "language": language,
                "model": model,
                "emergency": emergency,
                "escalation": escalation,
            }
        )
        collected: list[str] = []
        try:
            async for piece in stream_chat(messages, settings=settings, model=model):
                collected.append(piece)
                yield _sse({"type": "delta", "text": piece})
        except LLMError as exc:
            yield _sse({"type": "error", "message": str(exc)})
        except Exception:  # pragma: no cover - defensive
            yield _sse(
                {
                    "type": "error",
                    "message": "Something went wrong while generating the answer.",
                }
            )
        else:
            answer = "".join(collected).strip()
            if answer:
                store.add_message(session_id, "assistant", answer)
        yield _sse({"type": "done"})

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return the same {"error": ...} shape the frontend expects."""
    first = (exc.errors() or [{}])[0]
    field = ".".join(str(part) for part in first.get("loc", [])[1:]) or "request"
    return JSONResponse(
        status_code=422,
        content={"error": f"{field}: {first.get('msg', 'invalid value')}"},
    )


# --------------------------------------------------------------------------- #
# frontend (mounted last so /api/* wins)
# --------------------------------------------------------------------------- #
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
# GenAI Generated code - End
