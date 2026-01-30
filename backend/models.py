from database import Base
from sqlalchemy import Column, Integer, ARRAY,String, Text, DateTime,Boolean
from sqlalchemy.sql import func
class Article(Base):
    __tablename__ = 'article'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description= Column(Text, nullable=False)
    authors= Column(ARRAY(String), nullable=False)
    date= Column(String, nullable=False)
    category= Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())