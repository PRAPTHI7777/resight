from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone 
from fastapi import HTTPException, status
import models
from sqlalchemy.orm import Session

from fastapi import Depends
from database import get_db

from fastapi.security import OAuth2PasswordBearer
oauth2_scheme=OAuth2PasswordBearer(tokenUrl="login")

SECRET_KEY = "your-super-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt

def verify_token(token: str):
    try:
        # Decode and verify the JWT using our secret key
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        # Extract the email stored in the "sub" claim
        email = payload.get("sub")

        # If the email doesn't exist, the token is invalid
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        # Return the email to whoever called this function
        return email

    # If the token is expired, tampered with,
    # or signed using the wrong secret key
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    email = verify_token(token)

    user = db.query(models.User).filter(
        models.User.email == email
    ).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


    