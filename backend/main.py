from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import models
from database import engine
import articles
import psycopg2

app = FastAPI()

origins = [
    "http://localhost:5501",
    "http://127.0.0.1:5501",
    
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)


app.include_router(articles.router)
@app.get("/")
def root():
    return {"message":"Welcome to the Articles API"}
