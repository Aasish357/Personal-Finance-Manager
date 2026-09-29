from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rate_limit import login_limiter
from app.core.security import DUMMY_HASH, Security
from app.db.database import get_db
from app.db.models.user import User
from app.schemas.user import Token, User as UserSchema, UserCreate, UserLogin

router = APIRouter()


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Bug fix: the original code tried to set `password_hash` on the pydantic
    # UserCreate model (which has no such field) instead of on the DB model.
    new_user = User(
        name=user_in.name,
        email=user_in.email,
        password_hash=Security.hash_password(user_in.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    # Keyed on client IP *and* the email being tried, so one attacker cannot
    # lock out a real user, and one victim cannot be used to burn the quota
    # for everyone else.
    limiter_key = f"login:{request.client.host if request.client else 'unknown'}:{credentials.email.lower()}"

    blocked, retry_after = login_limiter.is_blocked(limiter_key)
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    db_user = db.query(User).filter(User.email == credentials.email).first()
    # Always run the hash comparison, even when the email is unknown, so the
    # response time doesn't reveal whether an account exists.
    stored_hash = db_user.password_hash if db_user else DUMMY_HASH
    password_ok = Security.verify_password(credentials.password, stored_hash)

    if not db_user or not password_ok:
        login_limiter.record_failure(limiter_key)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    login_limiter.reset(limiter_key)
    access_token = Security.create_access_token(subject=db_user.id)
    return Token(access_token=access_token, user=db_user)


@router.get("/me", response_model=UserSchema)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user
