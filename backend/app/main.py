from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logging_mw import RequestLogMiddleware, configure_logging
from app.routers import analytics, auth, episodes, ops, requests, users

configure_logging()

app = FastAPI(title="Dataset Request Desk", version="1.0.0")
app.add_middleware(RequestLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ops.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(requests.router)
app.include_router(episodes.router)
app.include_router(analytics.router)
