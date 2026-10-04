import json
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.models import User
from app.security import decode_access_token
from app.services.events import subscribe

router = APIRouter(tags=["ops"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


@router.get("/health")
def health(db: Annotated[Session, Depends(get_db)]) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}


def _operator_from_token(token: str) -> User:
    db = SessionLocal()
    try:
        try:
            payload = decode_access_token(token)
            user = db.get(User, int(payload["sub"]))
        except (jwt.InvalidTokenError, KeyError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        if user.role not in {"operator", "admin"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    finally:
        db.close()


@router.get("/api/events")
async def stream_events(token: Annotated[str, Depends(oauth2_scheme)]) -> StreamingResponse:
    _operator_from_token(token)

    async def gen():
        yield "event: ready\ndata: {}\n\n"
        async for item in subscribe():
            yield f"event: desk\ndata: {json.dumps(item)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
