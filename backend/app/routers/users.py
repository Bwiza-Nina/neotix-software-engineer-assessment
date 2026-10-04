from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import AdminUser, DbDep
from app.models import User
from app.schemas import UserCreateIn, UserOut, UserUpdateIn
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(_: AdminUser, db: DbDep) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(_: AdminUser, body: UserCreateIn, db: DbDep) -> User:
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        name=body.name,
        role=body.role,
        organisation=body.organisation,
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already exists") from exc
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(_: AdminUser, user_id: int, body: UserUpdateIn, db: DbDep) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return user
