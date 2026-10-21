from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import hashlib
import hmac
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from email_utils import send_otp_email
from auth_handler import create_access_token
from config import JWT_SECRET_KEY
import models
import schemas
from database import get_db
from utils import hash_password, verify_password
from fastapi.security import OAuth2PasswordRequestForm


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)
logger = logging.getLogger(__name__)
OTP_MAX_ATTEMPTS = 5


def _hash_otp(purpose: str, otp: str) -> str:
    message = f"{purpose}:{otp}".encode("utf-8")
    return hmac.new(
        JWT_SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _verify_otp(
    user: models.User,
    purpose: str,
    submitted_otp: str,
    db: Session,
) -> bool:
    if not user.otp or not user.otp.startswith(f"{purpose}:"):
        return False

    parts = user.otp.split(":")
    if len(parts) < 2:
        return False
    stored_otp = parts[1]
    if stored_otp == "locked":
        raise HTTPException(
            status_code=429,
            detail="Too many invalid verification attempts. Request a new code.",
        )
    attempts = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    otp_digest = _hash_otp(purpose, submitted_otp)
    is_legacy_otp = len(stored_otp) == 6 and stored_otp.isdigit()
    if hmac.compare_digest(stored_otp, otp_digest) or (
        is_legacy_otp and hmac.compare_digest(stored_otp, submitted_otp)
    ):
        return True

    attempts += 1
    if attempts >= OTP_MAX_ATTEMPTS:
        user.otp = f"{purpose}:locked"
        db.commit()
        raise HTTPException(
            status_code=429,
            detail="Too many invalid verification attempts. Request a new code.",
        )

    user.otp = f"{purpose}:{stored_otp}:{attempts}"
    db.commit()
    return False

@router.post("/signup", status_code=201)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(
        (models.User.email == user.email)
        | (models.User.username == user.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email or username is already registered"
        )

    hashed_pw = hash_password(user.password)

    signup_otp = f"{secrets.randbelow(900000) + 100000:06d}"
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pw,
        otp=f"signup:{_hash_otp('signup', signup_otp)}",
        otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email or username is already registered",
        ) from error
    db.refresh(new_user)

    try:
        send_otp_email(user.email, signup_otp)
    except (OSError, RuntimeError, smtplib.SMTPException) as error:
        db.delete(new_user)
        db.commit()
        logger.warning(
            "Signup verification email delivery failed (%s).",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not send the verification email. Check email "
                "configuration and try again."
            ),
        ) from error

    return {"message": "Verification code sent"}


@router.post("/verify-signup-otp")
def verify_signup_otp(
    request: schemas.ResetOtpVerificationRequest,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.otp or not user.otp.startswith("signup:"):
        raise HTTPException(status_code=400, detail="No signup verification is pending")
    if not user.otp_expires_at or datetime.now(timezone.utc) > user.otp_expires_at:
        user.otp = None
        user.otp_expires_at = None
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expired")
    if not _verify_otp(user, "signup", request.otp, db):
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user.otp = None
    user.otp_expires_at = None
    db.commit()
    return {"message": "Email verified"}


@router.post("/resend-signup-otp")
def resend_signup_otp(
    request: schemas.ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.otp or not user.otp.startswith("signup:"):
        raise HTTPException(status_code=400, detail="No signup verification is pending")
    if user.otp_expires_at and datetime.now(timezone.utc) < user.otp_expires_at:
        raise HTTPException(
            status_code=429,
            detail="A verification code was sent recently. Check your email.",
        )

    previous_otp = user.otp
    previous_expiry = user.otp_expires_at
    otp = f"{secrets.randbelow(900000) + 100000:06d}"
    user.otp = f"signup:{_hash_otp('signup', otp)}"
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    db.commit()
    try:
        send_otp_email(request.email, otp)
    except (OSError, RuntimeError, smtplib.SMTPException) as error:
        user.otp = previous_otp
        user.otp_expires_at = previous_expiry
        db.commit()
        logger.warning(
            "Signup verification email resend failed (%s).",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not send the verification email. Check email "
                "configuration and try again."
            ),
        ) from error
    return {"message": "Verification code sent"}


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

    if existing_user.otp and existing_user.otp.startswith("signup:"):
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in",
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


@router.post("/forgot-password")
def forgot_password(
    request: schemas.ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    generic_response = {
        "message": "If the email is registered, password-reset instructions will be sent."
    }
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()

    if not user:
        return generic_response

    if user.otp and user.otp.startswith("signup:"):
        return generic_response

    if (
        user.otp
        and user.otp.startswith("reset:")
        and user.otp_expires_at
        and datetime.now(timezone.utc) < user.otp_expires_at
    ):
        return generic_response

    otp = f"{secrets.randbelow(900000) + 100000:06d}"

    user.otp = f"reset:{_hash_otp('reset', otp)}"
    user.otp_expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=5)
    )

    db.commit()

    try:
        send_otp_email(request.email, otp)
    except (OSError, RuntimeError, smtplib.SMTPException) as error:
        user.otp = None
        user.otp_expires_at = None
        db.commit()
        logger.warning(
            "Password-reset email delivery failed (%s).",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not send the verification email. Check email "
                "configuration and try again."
            ),
        ) from error

    return generic_response
@router.post("/verify-reset-otp")
def verify_reset_otp(
    request: schemas.ResetOtpVerificationRequest,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code",
        )

    if not user.otp_expires_at:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code",
        )

    if datetime.now(timezone.utc) > user.otp_expires_at:
        user.otp = None
        user.otp_expires_at = None
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code",
        )

    if not _verify_otp(user, "reset", request.otp, db):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code",
        )

    user.otp = "reset-verified"
    db.commit()

    return {
        "message": "OTP verified"
    }

@router.post("/reset-password")
def reset_password(
    request: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code",
        )

    if user.otp != "reset-verified":
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code",
        )

    if not user.otp_expires_at:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code",
        )

    if datetime.now(timezone.utc) > user.otp_expires_at:
        user.otp = None
        user.otp_expires_at = None
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code",
        )

    user.hashed_password = hash_password(request.new_password)

    user.otp = None
    user.otp_expires_at = None

    db.commit()

    return {
        "message": "Password reset successfully"
    }
