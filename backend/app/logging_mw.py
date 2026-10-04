import json
import logging
import time
from collections.abc import Callable

import jwt
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger("desk.request")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        user_id = _user_id_from_auth(request.headers.get("authorization"))
        payload = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
        }
        logger.info(json.dumps(payload))
        return response


def _user_id_from_auth(header: str | None) -> int | None:
    if not header or not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return int(payload["sub"])
    except Exception:
        return None
