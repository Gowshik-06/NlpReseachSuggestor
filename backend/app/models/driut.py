"""
SQLAlchemy models for DRIUT (Dynamic Research Impact Update Tracker).
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class DRIUTAlert(Base):
    __tablename__ = "driut_alerts"
    __table_args__ = (
        UniqueConstraint("user_id", "saved_paper_id", "trigger_paper_id", name="uq_user_driut_alert"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), ForeignKey("users.username", ondelete="CASCADE"), default="default_user", index=True, nullable=False)
    saved_paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    trigger_paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    
    # 6 Taxonomy Types from PPTX: Extension, Improvement, Challenge, Reproduction, Alternative, Potential Replacement
    relationship_type = Column(String(50), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    explanation = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # TASK-15 Evidence Grounding & Provenance Fields
    evidence_strength = Column(String(50), nullable=True, default="tentative", index=True)  # strong_evidence, partial_evidence, tentative, insufficient_evidence
    evidence_passage = Column(Text, nullable=True)  # Supporting evidence passage from candidate paper
    saved_evidence_passage = Column(Text, nullable=True)  # Baseline passage from saved paper
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    section_name = Column(String(100), nullable=True)
    source_type = Column(String(50), nullable=True, default="abstract")  # abstract, full_text
    semantic_similarity = Column(Float, nullable=True)  # Tracked separately as topical signal, NOT proof of relationship
    comparability_notes = Column(Text, nullable=True)
    uncertainty_warning = Column(Text, nullable=True)
    classification_version = Column(String(50), nullable=True, default="v2.0-evidence-grounded", index=True)

    saved_paper = relationship("Paper", foreign_keys=[saved_paper_id])
    trigger_paper = relationship("Paper", foreign_keys=[trigger_paper_id])
    user = relationship("User", back_populates="driut_alerts", foreign_keys=[user_id])
