from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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

articles=[
  {
      "id": 1,
    "title": "Low-Power LoRaWAN Mesh Networks",
    "description": "Optimizing packet routing protocols for battery-operated sensors in remote agricultural monitoring.",
    "authors": ["Amina Okoro"],
    "date": "2025-08-19",
    "category": "IoT"
  },
  {  "id":2,
    "title": "Neuromorphic Computing Architectures",
    "description": "Comparative analysis of spikes-based processing versus traditional Von Neumann architectures for edge devices.",
    "authors": ["Dr. Hans Mueller", "Elena Rossi"],
    "date": "2025-12-01",
    "category": "Hardware"
  },
  {  "id":3,
    "title": "Zero-Knowledge Proofs in Supply Chains",
    "description": "Utilizing ZK-Snarks to verify origin authenticity without compromising proprietary vendor data.",
    "authors": ["Samir Bansal"],
    "date": "2026-01-03",
    "category": "Blockchain"
  },
  { "id":4,
    "title": "Natural Language Processing for Dead Languages",
    "description": "Using transformer models to reconstruct and translate fragmented inscriptions from ancient Sumerian texts.",
    "authors": ["Dr. Clara Oswald", "Miguel Hernandez"],
    "date": "2025-11-20",
    "category": "NLP"
  },
  { "id":5,
    "title": "Autonomous Drone Swarm Coordination",
    "description": "Implementing decentralized flocking algorithms for rapid search and rescue operations in disaster zones.",
    "authors": ["Sarah Jenkins", "Tariq Ali"],
    "date": "2025-09-15",
    "category": "Robotics"
  },
  { "id":5,
    "title": "Advancements in Solid-State Battery Tech",
    "description": "Research into ceramic electrolytes to increase energy density and safety in electric vehicle power cells.",
    "authors": ["Dr. Fiona Gallagher"],
    "date": "2025-07-08",
    "category": "Energy Tech"
  },
  { "id":6,
    "title": "Human-in-the-Loop Content Moderation",
    "description": "Examining the psychological impact and efficiency of hybrid AI-human moderation systems for social platforms.",
    "authors": ["Kevin Park", "Laura Vance"],
    "date": "2025-10-10",
    "category": "Human-Computer Interaction"
  }
]

class Article(BaseModel):
    id:int
    title: str
    description: str
    authors: List[str]
    date: str
    category: str

@app.get("/articles", response_model=List[Article])  
def read_articles():
   return articles

@app.get("/articles/{article_id}")
def get_articles(article_id: int):
    for article in articles:
        if article["id"]==article_id:
            return article
    return{"message":"Article not found"}

@app.post("/articles")
def add_article(article: Article):
    articles.append(article)
    return {"message": "Article added successfully"}

@app.get("/articles/search")
def search_articles(category: str):
    filtered = []
    for article in articles:
        if article["category"]==category:
            filtered.append(article)
    return filtered
 
@app.delete("/articles/{article_id}")
def delete_articles(article_id:int):
    for article in articles:
        if article["id"]==article_id:
            articles.remove(article)
            return{"message":"Article deleted successfully"}
    return{"message":"Article not found"}

#app.put("/articles/article_id")
