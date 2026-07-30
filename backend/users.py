from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from auth_handler import get_current_user
import models

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "email": current_user.email
    }