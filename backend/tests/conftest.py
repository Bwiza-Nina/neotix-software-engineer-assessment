from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Base, User
from app.security import hash_password

TEST_USERS = [
    {"email": "admin@example.com", "password": "admin123", "role": "admin", "name": "Ada Admin"},
    {"email": "ops1@example.com", "password": "ops123", "role": "operator", "name": "Olu Operator"},
    {"email": "client-a@example.com", "password": "client123", "role": "client", "name": "Acme", "organisation": "Acme"},
    {"email": "client-b@example.com", "password": "client123", "role": "client", "name": "Beta", "organisation": "Beta"},
]


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="session")
def password_hashes():
    unique = {row["password"] for row in TEST_USERS}
    return {password: hash_password(password) for password in unique}


@pytest.fixture(autouse=True)
def clean_db(engine, password_hashes):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        for row in TEST_USERS:
            db.add(
                User(
                    email=row["email"],
                    password_hash=password_hashes[row["password"]],
                    name=row["name"],
                    role=row["role"],
                    organisation=row.get("organisation"),
                    is_active=True,
                )
            )
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def db(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str) -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_csv() -> Path:
    candidates = [
        Path("/seed/episodes.csv"),
        Path(__file__).resolve().parents[2] / "seed" / "episodes.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("seed/episodes.csv not found")


SEED_CSV = _seed_csv()
