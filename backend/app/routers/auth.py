from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.deps import CurrentUser, DbDep
from app.models import User
from app.schemas import LoginIn, TokenOut, UserOut
from app.security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: DbDep) -> TokenOut:
    return _issue_token(db, body.email, body.password)


@router.post("/token", response_model=TokenOut)
def oauth_token(db: DbDep, form: OAuth2PasswordRequestForm = Depends()) -> TokenOut:
    return _issue_token(db, form.username, form.password)


def _issue_token(db: DbDep, email: str, password: str) -> TokenOut:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
