from typing import List, Literal
from fastapi import HTTPException, Depends, Header, Query
from sqlalchemy.orm import Session
from starlette import status
import hmac
import logging
import models
import schemas
from fastapi import APIRouter
import requests
from config import ARTICLE_ADMIN_TOKEN
from database import get_db

from arxiv_service import ArxivFeedError, fetch_papers

from gemini_service import generate_summaries

router = APIRouter(
    prefix="/articles",
    tags=["articles"]
)
logger = logging.getLogger(__name__)


def _require_article_admin_token(token: str | None) -> None:
    if not ARTICLE_ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Article administration is not configured.",
        )
    if not token or not hmac.compare_digest(token, ARTICLE_ADMIN_TOKEN):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to modify articles.",
        )


@router.get("/live")
def get_live_articles(
    query: str = "",
    sort_by: Literal["relevance", "submittedDate"] = "relevance",
    max_results: int = Query(default=10, ge=1, le=20),
):
    categories = {
        "": "All fields",
        "artificial intelligence": "Artificial Intelligence",
        "neuroscience": "Neuroscience",
        "robotics": "Robotics",
        "computer vision": "Computer Vision",
        "cybersecurity": "Cybersecurity",
        "quantum computing": "Quantum Computing",
        "software engineering": "Software",
        "renewable energy": "Energy Tech",
    }
    try:
        return fetch_papers(
            query,
            max_results=max_results,
            category=categories.get(query.strip().lower(), "Search Results"),
            sort_by=sort_by,
        )
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "unknown"
        response_body = error.response.text[:500] if error.response is not None else ""
        logger.warning(
            "arXiv HTTP error (%s): %s; response body: %s",
            status,
            error,
            response_body,
        )
        raise HTTPException(
            status_code=502,
            detail="The arXiv service is temporarily unavailable. Please try again.",
        ) from error
    except ArxivFeedError as error:
        logger.warning("arXiv returned an invalid feed: %s", error)
        raise HTTPException(
            status_code=502,
            detail="The arXiv service returned an invalid response. Please try again.",
        ) from error
    except requests.RequestException as error:
        logger.warning(
            "arXiv request failed (%s): %s",
            type(error).__name__,
            error,
        )
        raise HTTPException(
            status_code=502,
            detail="The arXiv service is temporarily unavailable. Please try again.",
        ) from error


@router.get('/',response_model=List[schemas.ArticleResponse])
def get_all(db: Session = Depends(get_db)):
    articles = db.query(models.Article).all()
    return articles

@router.post('/',status_code=status.HTTP_201_CREATED,response_model=List[schemas.ArticleResponse])
def create_article(
    article: schemas.ArticleCreate,
    db: Session = Depends(get_db),
    admin_token: str | None = Header(default=None, alias="X-Article-Admin-Token"),
):
    _require_article_admin_token(admin_token)
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
def delete_article(
    id: int,
    db: Session = Depends(get_db),
    admin_token: str | None = Header(default=None, alias="X-Article-Admin-Token"),
):
    _require_article_admin_token(admin_token)
    article = db.query(models.Article).filter(models.Article.id == id)
    if not article.first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Article with id: {id} does not exist")
    article.delete(synchronize_session=False)
    db.commit()

@router.put('/{id}',response_model=schemas.ArticleResponse)
def update_article(
    id: int,
    updated_article: schemas.ArticleCreate,
    db: Session = Depends(get_db),
    admin_token: str | None = Header(default=None, alias="X-Article-Admin-Token"),
):
   _require_article_admin_token(admin_token)
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
