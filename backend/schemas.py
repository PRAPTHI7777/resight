from pydantic import BaseModel
from datetime import datetime
from typing import List
class ArticleBase(BaseModel):
    title: str
    description: str
    authors: List[str]
    date: str
    category: str
      
    class Config:
        from_attributes = True
    
class ArticleCreate(ArticleBase):
    pass

class ArticleResponse(ArticleBase):
    id: int
    created_at: datetime
