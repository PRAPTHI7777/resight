from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import hmac
import logging
import secrets
import smtplib
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
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
logger = logging.getLogger(__name__)

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

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_pw,
        otp=f"signup:{secrets.randbelow(900000) + 100000:06d}",
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
        send_otp_email(user.email, new_user.otp.split(":", maxsplit=1)[1])
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
    if not hmac.compare_digest(user.otp.partition(":")[2], request.otp):
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
    user.otp = f"signup:{otp}"
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
    user = db.query(models.User).filter(
        models.User.email == request.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Email not registered"
        )

    if user.otp and user.otp.startswith("signup:"):
        raise HTTPException(
            status_code=400,
            detail="Please verify your email before resetting your password",
        )

    otp = f"{secrets.randbelow(900000) + 100000:06d}"

    user.otp = f"reset:{otp}"
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

    return {
        "message": "OTP sent successfully"
    }
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
            status_code=404,
            detail="User not found"
        )

    if (
        not user.otp
        or not user.otp.startswith("reset:")
        or not hmac.compare_digest(user.otp.partition(":")[2], request.otp)
    ):
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
        user.otp = None
        user.otp_expires_at = None
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
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
            status_code=404,
            detail="User not found"
        )

    if user.otp != "reset-verified":
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
        user.otp = None
        user.otp_expires_at = None
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="OTP expired"
        )

    user.hashed_password = hash_password(request.new_password)

    user.otp = None
    user.otp_expires_at = None

    db.commit()

    return {
        "message": "Password reset successfully"
    }
