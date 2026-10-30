"""
Administrator seed utility for ResearchLens.
Hardened against weak defaults and unintended execution.

Security rules:
- Requires strong explicitly configured credential via ADMIN_INITIAL_PASSWORD.
- Rejects known weak passwords.
- Blocks execution in production without explicit deployment authorization (ALLOW_PRODUCTION_ADMIN_SEED=1).
- Preserves existing administrator records without silently overwriting credentials.
- Never prints or logs plain passwords.
"""
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.db.session import SessionLocal
from app.models.user import User
from app.models.paper import Paper, SavedPaper
from app.models.driut import DRIUTAlert
from app.core.security import hash_password
from app.core.config import get_settings

WEAK_PASSWORDS = {"1234", "admin", "password", "12345678", "admin123", "admin1234"}


def validate_admin_password(password: Optional[str]) -> str:
    """Validate administrator password against project security policy."""
    if not password:
        raise ValueError("ADMIN_INITIAL_PASSWORD is required to seed the administrator account.")
    clean = password.strip()
    if clean.lower() in WEAK_PASSWORDS:
        raise ValueError("ADMIN_INITIAL_PASSWORD is too weak. Please provide a strong administrative credential.")
    if len(clean) < 8 or len(clean) > 128:
        raise ValueError("ADMIN_INITIAL_PASSWORD must be between 8 and 128 characters.")
    return clean


def seed_admin_user(initial_password: Optional[str] = None):
    """
    Seed administrator account with explicitly provided strong credential.
    Safe against accidental production execution and never overwrites existing passwords.
    """
    env = (os.environ.get("ENVIRONMENT") or getattr(get_settings(), "ENVIRONMENT", "development")).strip().lower()

    # Block unintended production execution
    if env == "production":
        allow_prod = os.environ.get("ALLOW_PRODUCTION_ADMIN_SEED", "").strip()
        if allow_prod not in ("1", "true", "yes"):
            raise RuntimeError(
                "Execution of administrator seed script in production is prohibited "
                "without explicit ALLOW_PRODUCTION_ADMIN_SEED=1 deployment authorization."
            )

    configured_pwd = initial_password or os.environ.get("ADMIN_INITIAL_PASSWORD")
    validated_pwd = validate_admin_password(configured_pwd)

    with SessionLocal() as db:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@researchlens.local",
                hashed_password=hash_password(validated_pwd),
                full_name="System Administrator",
                is_active=True,
                is_superuser=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"[Seed] Successfully created administrator user (ID={admin.id}).")
        else:
            print(f"[Seed] Administrator account already exists (ID={admin.id}); preserving existing credentials without modification.")

        # Ensure demo papers in library for demonstration
        candidate_ids = [71, 67, 72, 307]
        for pid in candidate_ids:
            paper = db.query(Paper).filter(Paper.id == pid).first()
            if not paper:
                continue
            existing_saved = db.query(SavedPaper).filter(
                SavedPaper.user_id == "admin",
                SavedPaper.paper_id == pid
            ).first()
            if not existing_saved:
                tags = ["quantum-ml", "foundations"] if pid == 71 else \
                       ["video-distillation", "diffusion"] if pid == 67 else \
                       ["graph-neural-networks", "bioinformatics"] if pid == 72 else \
                       ["multimodal", "agriculture"]
                sp = SavedPaper(
                    user_id="admin",
                    paper_id=pid,
                    notes=f"Curated benchmark paper ({paper.source.upper()}) for demonstration.",
                    tags=tags,
                )
                db.add(sp)
        db.commit()

        # Ensure DRIUT alerts for admin
        existing_alerts = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == "admin").count()
        if existing_alerts == 0:
            source_alerts = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == "testuser_task10").limit(8).all()
            for sa in source_alerts:
                new_alert = DRIUTAlert(
                    user_id="admin",
                    saved_paper_id=sa.saved_paper_id,
                    trigger_paper_id=sa.trigger_paper_id,
                    relationship_type=sa.relationship_type,
                    confidence_score=sa.confidence_score,
                    explanation=sa.explanation,
                    is_read=False,
                    evidence_strength=sa.evidence_strength or "strong_evidence",
                    evidence_passage=sa.evidence_passage or "Empirical benchmark evaluation demonstrating improved convergence.",
                    saved_evidence_passage=sa.saved_evidence_passage or "Baseline model error bounds on standard test splits.",
                    char_start=sa.char_start,
                    char_end=sa.char_end,
                    section_name=sa.section_name or "Results & Comparison",
                    source_type=sa.source_type or "abstract",
                    semantic_similarity=sa.semantic_similarity or 0.82,
                    comparability_notes=sa.comparability_notes or "Evaluated under identical evaluation protocols.",
                    classification_version=sa.classification_version or "v2.0-evidence-grounded",
                )
                db.add(new_alert)
            db.commit()

        saved_count = db.query(SavedPaper).filter(SavedPaper.user_id == "admin").count()
        alert_count = db.query(DRIUTAlert).filter(DRIUTAlert.user_id == "admin").count()
        print(f"[Seed] Admin user active with {saved_count} saved papers and {alert_count} DRIUT alerts.")


if __name__ == "__main__":
    seed_admin_user()
