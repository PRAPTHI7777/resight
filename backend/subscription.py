from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from auth_handler import get_current_user
from email_service import send_email


router = APIRouter(
    prefix="/subscription",
    tags=["Subscription"]
)


@router.post("/subscribe")
def subscribe(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    current_user.is_subscribed = True

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Successfully subscribed",
        "is_subscribed": current_user.is_subscribed
    }


@router.post("/unsubscribe")
def unsubscribe(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    current_user.is_subscribed = False

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Successfully unsubscribed",
        "is_subscribed": current_user.is_subscribed
    }


@router.get("/status")
def subscription_status(
    current_user: models.User = Depends(get_current_user)
):

    return {
        "is_subscribed": current_user.is_subscribed
    }


@router.post("/test-email")
def test_email(
    current_user: models.User = Depends(get_current_user)
):

    send_email(
        current_user.email,
        "Resight Email Test",
        "Hello!\n\nThis is a test email from Resight.\n\nYour email system is working! 📧"
    )

    return {
        "message": "Test email sent successfully",
        "email": current_user.email
    }