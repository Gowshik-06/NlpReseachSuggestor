"""
SQLAlchemy models for research papers and user saved library.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Float, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(String(120), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False, index=True)
    abstract = Column(Text, nullable=True)
    authors = Column(JSON, nullable=False, default=list)  # list of strings
    venue = Column(String(255), nullable=True)
    year = Column(Integer, nullable=True, index=True)
    doi = Column(String(255), nullable=True, index=True)
    url = Column(String(500), nullable=True)
    pdf_url = Column(String(500), nullable=True)
    source = Column(String(50), nullable=False, default="local", index=True)  # arxiv, semantic_scholar, crossref, core, dblp, local
    citation_count = Column(Integer, default=0)
    categories = Column(JSON, default=list)  # list of subject categories
    raw_text = Column(Text, nullable=True)  # full text extracted from PDF if uploaded
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    saved_entries = relationship("SavedPaper", back_populates="paper", cascade="all, delete-orphan")
    evidence_records = relationship("PaperEvidence", back_populates="paper", cascade="all, delete-orphan")


class SavedPaper(Base):
    __tablename__ = "saved_papers"
    __table_args__ = (
        UniqueConstraint("user_id", "paper_id", name="uq_user_saved_paper"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), ForeignKey("users.username", ondelete="CASCADE"), default="default_user", index=True, nullable=False)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=list)
    saved_at = Column(DateTime(timezone=True), server_default=func.now())

    paper = relationship("Paper", back_populates="saved_entries")
    user = relationship("User", back_populates="saved_papers", foreign_keys=[user_id])
