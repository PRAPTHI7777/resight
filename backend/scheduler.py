from apscheduler.schedulers.background import BackgroundScheduler

from database import SessionLocal
from digest import create_digest_email
from arxiv_service import fetch_papers
from email_service import send_email
import models


scheduler = BackgroundScheduler()


def send_scheduled_digest():

    db = SessionLocal()

    try:

        print("Starting scheduled Resight digest...")

        papers = fetch_papers("artificial intelligence")

        html_body = create_digest_email(papers)

        subscribers = db.query(models.User).filter(
            models.User.is_subscribed == True
        ).all()

        for user in subscribers:

            send_email(
                user.email,
                "Your Resight Research Digest",
                html_body
            )

        print(
            f"Digest sent to {len(subscribers)} subscribers."
        )

    except Exception as error:

        print("Scheduled digest error:", error)

    finally:

        db.close()


def start_scheduler():

    # TEST: run every 2 minutes
    scheduler.add_job(
        send_scheduled_digest,
        "interval",
        minutes=2,
        id="resight_digest",
        replace_existing=True
    )

    scheduler.start()

    print("Resight scheduler started.")