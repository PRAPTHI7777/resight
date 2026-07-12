from database import Base
from sqlalchemy import Column, ForeignKey, Integer, ARRAY,String, Text, DateTime,Boolean, UniqueConstraint
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

class User(Base):
    __tablename__='user'
    id = Column(Integer, primary_key=True, index=True)
    username=Column(String,nullable=False,unique=True)
    email=Column(String,nullable=False,unique=True)
    hashed_password=Column(String,nullable=False)
    is_subscribed=Column(Boolean,default=False)
    created_at=Column(DateTime(timezone=True), server_default=func.now())

class Bookmark(Base):
    __tablename__='bookmark'
    id=Column(Integer,primary_key=True,index=True)
    user_id=Column(Integer, ForeignKey("user.id"))
    paper_id=Column(Integer,nullable=False)
    created_at=Column(DateTime(timezone=True),server_default=func.now())
   #composite unique constraint:same user can't bookmark the same paper twice, even if two requests arrive simultaneously
    __table_args__ = (
        UniqueConstraint("user_id", "paper_id", name="unique_user_bookmark"),
    )
