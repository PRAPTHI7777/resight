from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import models
from database import get_db
from auth_handler import get_current_user

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