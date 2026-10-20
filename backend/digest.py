from fastapi import APIRouter, Depends, HTTPException
from html import escape
import logging
import requests
from sqlalchemy.orm import Session

import models
from database import get_db
from auth_handler import get_current_user
from arxiv_service import fetch_papers
from email_service import send_email


router = APIRouter(
    prefix="/digest",
    tags=["Digest"]
)
logger = logging.getLogger(__name__)


# Research fields included in the digest
DIGEST_FIELDS = {
    "Artificial Intelligence": "artificial intelligence",
    "Robotics": "robotics",
    "Cybersecurity": "cybersecurity",
    "Quantum Computing": "quantum computing",
    "Software": "software engineering",
    "Energy Tech": "renewable energy"
}


def create_digest_email(papers):

    html = """
    <!DOCTYPE html>
    <html>
    <body style="
        margin: 0;
        padding: 0;
        background-color: #f5f5f5;
        font-family: Arial, sans-serif;
    ">

        <div style="
            max-width: 700px;
            margin: 30px auto;
            background: white;
            padding: 40px;
        ">

            <h1 style="
                text-align: center;
                font-family: Georgia, serif;
                letter-spacing: 3px;
                margin-bottom: 5px;
            ">
                RESIGHT
            </h1>

            <p style="
                text-align: center;
                color: #777;
                margin-bottom: 40px;
            ">
                Research Digest
            </p>
    """

    for paper in papers:

        html += f"""
            <div style="
                margin-bottom: 35px;
                padding-bottom: 25px;
                border-bottom: 1px solid #ddd;
            ">

                <p style="
                    color: #777;
                    font-size: 12px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                ">
                    {escape(str(paper["category"]))}
                </p>

                <h2 style="
                    font-family: Georgia, serif;
                    font-size: 21px;
                    line-height: 1.4;
                ">
                    {escape(str(paper["title"]))}
                </h2>

                <p style="
                    color: #777;
                    font-size: 13px;
                ">
                    {escape(", ".join(paper["authors"]))}
                </p>

                <p style="
                    font-size: 15px;
                    line-height: 1.7;
                    color: #333;
                ">
                    {escape(str(paper["description"]))}
                </p>

                <a href="{escape(str(paper["link"]), quote=True)}"
                   style="
                       display: inline-block;
                       margin-top: 10px;
                       padding: 10px 18px;
                       background-color: #111;
                       color: white;
                       text-decoration: none;
                       border-radius: 4px;
                   ">
                    Read Original Paper →
                </a>

            </div>
        """

    html += """
            <p style="
                text-align: center;
                color: #999;
                font-size: 12px;
                margin-top: 30px;
            ">
                You are receiving this because you subscribed
                to Resight research digests.
            </p>

        </div>

    </body>
    </html>
    """

    return html


@router.post("/send")
def send_digest(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):

    logger.info("Manual digest requested by user id %s.", current_user.id)
    all_papers = []

    # Fetch papers from every research field
    try:
        for category, query in DIGEST_FIELDS.items():
            papers = fetch_papers(query, max_results=2)

            for paper in papers:
                paper["category"] = category

            all_papers.extend(papers)
    except requests.RequestException as error:
        logger.warning("arXiv digest fetch failed (%s).", type(error).__name__)
        raise HTTPException(
            status_code=502,
            detail="The arXiv service is temporarily unavailable. Please try again.",
        ) from error

    html_body = create_digest_email(all_papers)

    subscribers = db.query(models.User).filter(
        models.User.is_subscribed == True
    ).all()

    for user in subscribers:

        send_email(
            user.email,
            "Your Resight Research Digest",
            html_body
        )

    return {
        "message": "Digest sent successfully",
        "subscribers": len(subscribers),
        "papers": len(all_papers)
    }