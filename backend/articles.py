from typing import List
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from starlette import status
import models
import schemas
from fastapi import APIRouter
from database import get_db

router = APIRouter(
    prefix="/articles",
    tags=["articles"]
)


@router.get('/',response_model=List[schemas.ArticleResponse])
def get_all(db: Session = Depends(get_db)):
    articles = db.query(models.Article).all()
    return articles

@router.post('/',status_code=status.HTTP_201_CREATED,response_model=List[schemas.ArticleResponse])
def create_article(article: schemas.ArticleCreate, db: Session = Depends(get_db)):
    new_article = models.Article(**article.dict())
    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    return [new_article]
        
@router.get('/{id}',response_model=schemas.ArticleResponse)
def get_article(id:int, db: Session = Depends(get_db)):
    article = db.query(models.Article).filter(models.Article.id == id).first()
    if not article:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Article with id: {id} was not found")
    return article

@router.delete('/{id}',status_code=status.HTTP_204_NO_CONTENT)
def delete_article(id:int,db: Session = Depends(get_db)):
    article = db.query(models.Article).filter(models.Article.id == id)
    if not article.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Article with id: {id} does not exist")
    article.delete(synchronize_session=False)
    db.commit()

@router.put('/{id}',response_model=schemas.ArticleResponse)
def update_article(id:int , updated_article: schemas.ArticleCreate, db: Session = Depends(get_db)):
   article = db.query(models.Article).filter(models.Article.id == id)
   if article.first() is None:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Article with id: {id} does not exist")
   article.update(updated_article.dict(),synchronize_session=False)
   db.commit()
   return article.first()

@router.get('/category/{category}',response_model=List[schemas.ArticleResponse])
def get_articles_by_category(category: str, db: Session = Depends(get_db)):
    articles = db.query(models.Article).filter(models.Article.category == category).all()
    return articles