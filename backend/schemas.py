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

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password:str

class UserResponse(UserBase):
    id:int
    is_subscribed:bool
    created_at:datetime
    
    class Config:
        from_attributes=True

class UserLogin(BaseModel):
    email:str
    password:str
