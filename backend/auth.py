from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import random
from datetime import datetime, timedelta, timezone

from email_utils import send_otp_email
from auth_handler import create_access_token
import models
import schemas
from database import get_db
from utils import hash_password, verify_password

from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post("/signup", response_model=schemas.UserResponse)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    hashed_pw = hash_password(user.password)

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pw
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(
        models.User.email == form_data.username
    ).first()

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        form_data.password,
        existing_user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = create_access_token(
        {"sub": existing_user.email}
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@router.post("/send-otp")
def send_otp(
    user: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(
        models.User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    otp = str(random.randint(100000, 999999))

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    hashed_pw = hash_password(user.password)

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pw,
        otp=otp,
        otp_expires_at=expires_at,
        is_verified=False
    )

    db.add(new_user)
    db.commit()

    send_otp_email(user.email, otp)

    return {
        "message": "OTP sent successfully"
    }

@router.post("/verify-otp")
def verify_otp(
    email: str,
    otp: str,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.is_verified:
        raise HTTPException(
            status_code=400,
            detail="Email already verified"
        )

    if user.otp != otp:
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP"
        )

    if not user.otp_expires_at:
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
        )

    if datetime.now(timezone.utc) > user.otp_expires_at:
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
        )

    user.is_verified = True
    user.otp = None
    user.otp_expires_at = None

    db.commit()

    return {
        "message": "Email verified successfully"
    }

@router.post("/forgot-password")
def forgot_password(
    email: str,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Email not registered"
        )

    otp = str(random.randint(100000, 999999))

    user.otp = otp
    user.otp_expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    )

    db.commit()

    send_otp_email(email, otp)

    return {
        "message": "OTP sent successfully"
    }
@router.post("/verify-reset-otp")
def verify_reset_otp(
    email: str,
    otp: str,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if user.otp != otp:
        raise HTTPException(
            status_code=400,
            detail="Invalid OTP"
        )

    if not user.otp_expires_at:
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
        )

    if datetime.now(timezone.utc) > user.otp_expires_at:
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
        )

    return {
        "message": "OTP verified"
    }

@router.post("/reset-password")
def reset_password(
    email: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    if not user.otp:
        raise HTTPException(
            status_code=400,
            detail="Please verify OTP first"
        )

    if not user.otp_expires_at:
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
        )

    if datetime.now(timezone.utc) > user.otp_expires_at:
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
        )

    user.hashed_password = hash_password(new_password)

    user.otp = None
    user.otp_expires_at = None

    db.commit()

    return {
        "message": "Password reset successfully"
    }