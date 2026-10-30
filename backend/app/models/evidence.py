"""
SQLAlchemy model for research evidence extracted from academic papers.
Grounded evidence links specific scientific claims to verified source passages.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class PaperEvidence(Base):
    """
    Evidence record representing an author-stated claim grounded in a specific source passage.
    Tracks exact character offsets, section/page provenance, and source document hash.
    """
    __tablename__ = "paper_evidence"
    __table_args__ = (
        UniqueConstraint("paper_id", "category", "char_start", "char_end", name="uq_paper_evidence_span"),
    )

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    claim = Column(Text, nullable=False)
    source_passage = Column(Text, nullable=False)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    page_number = Column(Integer, nullable=True)
    section_name = Column(String(100), nullable=True)
    source_type = Column(String(50), nullable=False, default="abstract", index=True)  # abstract, full_text, title
    extraction_method = Column(String(50), nullable=False, default="rule_based_nlp")
    confidence_score = Column(Float, nullable=True)
    is_verified = Column(Boolean, nullable=False, default=True)
    verification_notes = Column(String(255), nullable=True)
    source_hash = Column(String(64), nullable=True, index=True)  # SHA256 of source text at extraction time
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    paper = relationship("Paper", back_populates="evidence_records")
