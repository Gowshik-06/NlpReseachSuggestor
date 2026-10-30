"""
SQLAlchemy model for application users and credentials.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    firebase_uid = Column(String(128), unique=True, index=True, nullable=True)
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    saved_papers = relationship("SavedPaper", back_populates="user", cascade="all, delete-orphan", foreign_keys="SavedPaper.user_id")
    driut_alerts = relationship("DRIUTAlert", back_populates="user", cascade="all, delete-orphan", foreign_keys="DRIUTAlert.user_id")
