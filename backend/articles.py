from typing import List
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from starlette import status
import models
import schemas
from fastapi import APIRouter
import logging
import requests
from database import get_db

from arxiv_service import fetch_papers

from gemini_service import generate_summaries

router = APIRouter(
    prefix="/articles",
    tags=["articles"]
)
logger = logging.getLogger(__name__)

@router.get("/live")
def get_live_articles(query: str = "artificial intelligence"):
    categories = {
        "artificial intelligence": "Artificial Intelligence",
        "robotics": "Robotics",
        "cybersecurity": "Cybersecurity",
        "quantum computing": "Quantum Computing",
        "software engineering": "Software",
        "renewable energy": "Energy Tech",
    }
    try:
        return fetch_papers(
            query,
            category=categories.get(query.strip().lower(), "Search Results"),
        )
    except requests.RequestException as error:
        logger.warning("arXiv request failed (%s).", type(error).__name__)
        raise HTTPException(
            status_code=502,
            detail="The arXiv service is temporarily unavailable. Please try again.",
        ) from error


@router.get('/',response_model=List[schemas.ArticleResponse])
def get_all(db: Session = Depends(get_db)):
    articles = db.query(models.Article).all()
    return articles

@router.post('/',status_code=status.HTTP_201_CREATED,response_model=List[schemas.ArticleResponse])
def create_article(article: schemas.ArticleCreate, db: Session = Depends(get_db)):
    new_article = models.Article(**article.model_dump())
    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    return [new_article]


@router.get("/test-gemini")
def test_gemini():

    result = generate_summaries([{
        "title": "Artificial Intelligence",
        "abstract": (
            "Artificial intelligence systems can learn patterns from large "
            "datasets and use those patterns to make predictions."
        ),
    }])[0]

    return {
        "summary": result["summary"],
        "summary_source": result["source"],
    }

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
   article.update(updated_article.model_dump(),synchronize_session=False)
   db.commit()
   return article.first()

@router.get('/category/{category}',response_model=List[schemas.ArticleResponse])
def get_articles_by_category(category: str, db: Session = Depends(get_db)):
    articles = db.query(models.Article).filter(models.Article.category == category).all()
    return articles
