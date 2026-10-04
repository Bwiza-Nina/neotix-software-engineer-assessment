"""Create seed users from seed/users.json. Passwords are hashed with bcrypt; never stored plaintext."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import User
from app.security import hash_password


def seed_users() -> None:
    path = Path(settings.seed_users_path)
    if not path.exists():
        fallback = Path(__file__).resolve().parents[2] / "seed" / "users.json"
        path = fallback if fallback.exists() else path
    if not path.exists():
        print(f"No seed users file at {path}; skipping")
        return

    rows = json.loads(path.read_text())
    db = SessionLocal()
    try:
        created = 0
        for row in rows:
            email = row["email"].lower()
            exists = db.scalar(select(User).where(User.email == email))
            if exists:
                continue
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(row["password"]),
                    name=row["name"],
                    role=row["role"],
                    organisation=row.get("organisation"),
                    is_active=True,
                )
            )
            created += 1
        db.commit()
        print(f"Seeded {created} users")
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
