from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.orm import Session
import models,schemas
from database import get_db
from auth_handler import get_current_user

router=APIRouter(
    prefix="/bookmarks",
    tags=["Bookmarks"]
)

@router.post("/",response_model=schemas.BookmarkResponse)
def add_bookmark(
    Bookmark:schemas.BookmarkCreate,
    db:Session=Depends(get_db),
    current_user=Depends(get_current_user)):
    existing=db.query(models.Bookmark).filter(
        models.Bookmark.user_id==current_user.id,
        models.Bookmark.article_id==Bookmark.article_id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Bookmark already exists"
        )
    new_bookmark=models.Bookmark(
        user_id=current_user.id,
        article_id=Bookmark.article_id
    )
    db.add(new_bookmark)
    db.commit()
    db.refresh(new_bookmark)
    return new_bookmark
    
@router.get("/", response_model=list[schemas.BookmarkResponse])
def get_bookmarks(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    bookmarks = db.query(models.Bookmark).filter(
        models.Bookmark.user_id == current_user.id
    ).all()

    return bookmarks

@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bookmark(
    article_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    bookmark = db.query(models.Bookmark).filter(
        models.Bookmark.user_id == current_user.id,
        models.Bookmark.article_id == article_id
    ).first()

    if bookmark is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found"
        )

    db.delete(bookmark)
    db.commit()