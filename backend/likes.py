from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.orm import Session
import models,schemas
from database import get_db
from auth_handler import get_current_user

router=APIRouter(
    prefix="/likes",
    tags=["Likes"]
)

@router.post("/",response_model=schemas.LikeResponse)
def add_like(
    Like:schemas.LikeCreate,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)):
    existing=db.query(models.Like).filter(
        models.Like.user_id==current_user.id,
        models.Like.article_id==Like.article_id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Like already exists"
        )
    new_like=models.Like(
        user_id=current_user.id,
        article_id=Like.article_id,
        title=Like.title,
        authors=Like.authors,
        summary=Like.summary,
        link=Like.link
    )
    db.add(new_like)
    db.commit()
    db.refresh(new_like)
    return new_like

@router.get("/", response_model=list[schemas.LikeResponse])
def get_likes(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    likes = db.query(models.Like).filter(
        models.Like.user_id == current_user.id
    ).all()

    return likes

@router.delete("/{id}")
def delete_like(
    id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    like = db.query(models.Like).filter(
        models.Like.id == id,
        models.Like.user_id == current_user.id
    ).first()

    if like is None:
        raise HTTPException(
            status_code=404,
            detail="Like not found"
        )

    db.delete(like)
    db.commit()