"""
FastAPI endpoints for research paper discovery, PDF upload, recommendations, comparison, and DRIUT.
"""
import hashlib
import uuid
import re
from typing import List, Optional, Union, Dict, Any, Tuple
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models import User, Paper, SavedPaper, DRIUTAlert, PaperEvidence
from app.api.deps import get_current_user
from datetime import datetime, timezone

logger = get_logger(__name__)
from app.services.vector_index import (
    reindex_vector_database,
    get_index_consistency_status,
    ReindexInProgressError,
    sync_unindexed_papers,
    get_faiss_index
)
from app.services.deduplication import normalize_title, compute_title_jaccard_similarity
from app.schemas.paper import (
    SearchQueryRequest,
    SearchResponse,
    CompareRequest,
    CompareResponse,
    SummaryResponse,
    SavePaperRequest,
    SavedPaperResponse,
    DRIUTAlertResponse,
    DRIUTScanResponse,
    DRIUTStatusResponse,
    PaperResponse,
    PaperBase,
    PaperSummaryRequest,
    TransientEvidenceRequest,
    PdfPreviewResponse,
    PdfIngestRequest,
    PdfIngestResponse,
    DuplicateMatchDetail,
    ExtractedMetadata,
)
from app.services.pdf_service import extract_text_from_pdf_bytes
from app.services.recommendation_engine import execute_recommendation_search
from app.services.summary_service import generate_paper_summary
from app.services.comparison_service import compare_papers
from app.services.driut_service import scan_saved_papers_for_updates
from app.services.driut_scheduler import driut_scheduler
from app.schemas.evidence import (
    PaperEvidenceResponse,
    EvidenceExtractionRequest,
    ALL_EVIDENCE_CATEGORIES,
    CATEGORY_LABELS,
    EvidenceItemResponse,
    EvidenceVerificationSummary,
)
from app.services.evidence_service import (
    extract_and_persist_paper_evidence,
    get_paper_evidence,
    verify_evidence_record,
    extract_evidence_from_text,
    compute_source_hash,
)

router = APIRouter()


@router.post("/search", response_model=SearchResponse, summary="Hybrid Semantic Search & Recommendation")
async def search_papers(
    req: SearchQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Search papers across local repository and external APIs (arXiv, Semantic Scholar, Crossref, DBLP).
    Performs FAISS semantic vector search and produces explainable recommendations.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")
    return await execute_recommendation_search(db, req)


async def _read_and_validate_pdf_upload(file: UploadFile, max_bytes: int) -> bytes:
    """
    Read uploaded file stream into memory with validation:
    1. Validate .pdf filename extension
    2. Enforce configurable MAX_UPLOAD_SIZE_BYTES limits (HTTP 413)
    3. Inspect magic bytes header (%PDF-) to prevent renaming attacks
    4. Reject 0-byte empty files
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    chunk_size = 64 * 1024  # 64 KB chunks
    buffer = bytearray()

    first_chunk = await file.read(chunk_size)
    if not first_chunk:
        await file.close()
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    if not first_chunk.startswith(b"%PDF-"):
        await file.close()
        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file format: file does not start with valid PDF magic bytes."
        )

    if len(first_chunk) > max_bytes:
        await file.close()
        max_mb = max(1, max_bytes // (1024 * 1024))
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds maximum allowed size of {max_mb} MB."
        )

    buffer.extend(first_chunk)

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            await file.close()
            max_mb = max(1, max_bytes // (1024 * 1024))
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded file exceeds maximum allowed size of {max_mb} MB."
            )

    await file.close()
    return bytes(buffer)


def _check_catalog_duplicate(db: Session, title: str, doi: Optional[str] = None) -> DuplicateMatchDetail:
    """
    Check if a candidate manuscript is a duplicate of an existing catalog paper.
    Pure read-only evaluation:
    1. Exact DOI match in PostgreSQL
    2. Exact normalized title match in PostgreSQL
    3. High title token Jaccard similarity (>= 0.85) in PostgreSQL
    """
    if doi:
        clean_doi = str(doi).strip().lower()
        if clean_doi:
            matched_doi = db.query(Paper).filter(func.lower(Paper.doi) == clean_doi).first()
            if matched_doi:
                return DuplicateMatchDetail(
                    is_duplicate=True,
                    match_type="exact_doi",
                    matched_paper_id=matched_doi.paper_id,
                    matched_catalog_id=matched_doi.id,
                    matched_title=matched_doi.title,
                    similarity_score=1.0,
                    explanation=f"Exact DOI match found in catalog: {matched_doi.doi}"
                )

    norm_cand_title = normalize_title(title)
    if not norm_cand_title:
        return DuplicateMatchDetail(is_duplicate=False)

    catalog_papers = db.query(Paper.id, Paper.paper_id, Paper.title).all()
    best_sim = 0.0
    best_match = None

    for p in catalog_papers:
        norm_p_title = normalize_title(p.title)
        if norm_p_title and norm_cand_title == norm_p_title:
            return DuplicateMatchDetail(
                is_duplicate=True,
                match_type="exact_title",
                matched_paper_id=p.paper_id,
                matched_catalog_id=p.id,
                matched_title=p.title,
                similarity_score=1.0,
                explanation=f"Exact normalized title match in catalog: '{p.title}'"
            )

        sim = compute_title_jaccard_similarity(title, p.title)
        if sim > best_sim:
            best_sim = sim
            best_match = p

    if best_sim >= 0.85 and best_match:
        return DuplicateMatchDetail(
            is_duplicate=True,
            match_type="high_title_similarity",
            matched_paper_id=best_match.paper_id,
            matched_catalog_id=best_match.id,
            matched_title=best_match.title,
            similarity_score=round(best_sim, 2),
            explanation=f"High title similarity ({best_sim:.2f}) with catalog paper '{best_match.title}'"
        )

    return DuplicateMatchDetail(is_duplicate=False)


@router.post("/preview-pdf", response_model=PdfPreviewResponse, summary="PDF Manuscript Preview & Duplicate Analysis")
async def preview_pdf_paper(
    file: UploadFile = File(...),
    limit: Optional[int] = Query(None),
    limit_form: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload and parse research paper PDF in preview mode.
    Extracts title, abstract, authors, year, DOI, venue, and keywords without side effects.
    Evaluates catalog duplicate status read-only.
    Retrieves transient literature recommendations without mutating PostgreSQL, FAISS, or DRIUT.
    """
    effective_limit = limit if limit is not None else (limit_form if limit_form is not None else 10)
    settings = get_settings()
    content = await _read_and_validate_pdf_upload(file, settings.MAX_UPLOAD_SIZE_BYTES)

    extracted = extract_text_from_pdf_bytes(content)
    if not extracted["success"]:
        raise HTTPException(status_code=422, detail=f"PDF extraction error: {extracted['error']}")

    raw_text = (extracted.get("raw_text") or "").strip()
    if not raw_text:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in PDF. Scanned PDFs without embedded text or OCR are not supported."
        )

    title = (extracted.get("title") or "").strip()
    abstract = (extracted.get("abstract") or "").strip()
    if not title and not abstract and len(raw_text) < 20:
        raise HTTPException(
            status_code=422,
            detail="Insufficient extractable text content to generate literature recommendations."
        )

    if not title or title == "Untitled Research Paper":
        fallback_title = file.filename.replace(".pdf", "").replace("_", " ").strip()
        title = fallback_title or "Research Manuscript"

    authors = extracted.get("authors") or []
    year = extracted.get("year")
    doi = extracted.get("doi")
    venue = extracted.get("venue")
    keywords = extracted.get("keywords") or []
    page_count = extracted.get("page_count", 1)

    # 1. Read-only duplicate check against local catalog
    dup = _check_catalog_duplicate(db, title=title, doi=doi)

    # 2. Retrieve transient recommendations (side-effect-free)
    query_text = f"{title}. {abstract}".strip() if abstract else f"{title}. {raw_text[:500]}".strip()
    search_req = SearchQueryRequest(
        query=query_text,
        mode="pdf",
        limit=effective_limit,
        sources=["local", "arxiv", "semanticscholar", "crossref", "dblp", "pubmed", "csir"]
    )
    recommendations: List[PaperResponse] = []
    rec_warning: Optional[str] = None
    try:
        search_res = await execute_recommendation_search(db, search_req)
        recommendations = search_res.results
    except Exception as e:
        logger.warning("Preview recommendation search failed: %s", e)
        rec_warning = "Literature recommendations currently unavailable; you may still review metadata and ingest manuscript."

    warnings: List[str] = []
    if rec_warning:
        warnings.append(rec_warning)
    if not abstract:
        warnings.append("No explicit abstract section detected in manuscript; title and text preview will be used.")
    if not authors:
        warnings.append("Author names could not be automatically extracted; please verify before ingesting.")
    if dup.is_duplicate:
        warnings.append(f"Catalog duplicate detected: {dup.explanation}")

    return PdfPreviewResponse(
        filename=file.filename or "manuscript.pdf",
        status="duplicate" if dup.is_duplicate else "preview_ready",
        extracted_metadata=ExtractedMetadata(
            title=title,
            abstract=abstract or None,
            authors=authors,
            year=year,
            doi=doi,
            venue=venue,
            keywords=keywords
        ),
        page_count=page_count,
        raw_text_preview=raw_text[:1200],
        raw_text_length=len(raw_text),
        duplicate_check=dup,
        allow_ingest=not dup.is_duplicate,
        recommendations=recommendations,
        warnings=warnings
    )


@router.post("/ingest-pdf", response_model=PdfIngestResponse, summary="Explicit PDF Catalog Ingestion")
def ingest_pdf_manuscript(
    req: PdfIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Explicitly persist an extracted PDF manuscript to the local PostgreSQL catalog and FAISS index.
    Requires authenticated user and confirm_ingest=True.
    Guarantees duplicate prevention, transactional persistence, and atomic index synchronization.
    """
    if not req.confirm_ingest:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit confirmation (confirm_ingest=True) is required to add manuscript to the catalog."
        )

    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Manuscript title cannot be empty.")

    # Recheck duplicate status against current database catalog
    dup = _check_catalog_duplicate(db, title=title, doi=req.doi)
    if dup.is_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot ingest duplicate manuscript: {dup.explanation} (Matched Catalog ID: {dup.matched_catalog_id})."
        )

    # Generate stable repository-qualified paper_id
    if req.doi:
        clean_doi = str(req.doi).strip()
        paper_id = f"doi:{clean_doi}"
    else:
        clean_slug = re.sub(r"[^\w\s-]", "", title.lower())
        slug_prefix = "-".join(clean_slug.split()[:5])[:40]
        year_str = str(req.year) if req.year else "nodate"
        hash_tag = hashlib.sha256(f"{title}_{year_str}".encode("utf-8")).hexdigest()[:8]
        paper_id = f"pdf:{slug_prefix}_{hash_tag}" if slug_prefix else f"pdf:manuscript_{hash_tag}"

    existing_pid = db.query(Paper).filter(Paper.paper_id == paper_id).first()
    if existing_pid:
        paper_id = f"{paper_id}_{uuid.uuid4().hex[:6]}"

    new_paper = Paper(
        paper_id=paper_id,
        title=title[:500],
        abstract=(req.abstract or "").strip()[:50000] if req.abstract else None,
        authors=req.authors or ["Unknown"],
        venue=(req.venue or "").strip()[:255] if req.venue else "Uploaded Manuscript",
        year=req.year or datetime.now().year,
        doi=str(req.doi).strip()[:255] if req.doi else None,
        source="pdf_upload",
        citation_count=0,
        categories=req.keywords or ["cs.AI"]
    )

    try:
        db.add(new_paper)
        db.commit()
        db.refresh(new_paper)
    except IntegrityError:
        db.rollback()
        existing = db.query(Paper).filter(Paper.paper_id == paper_id).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Manuscript with identifier '{paper_id}' was ingested concurrently."
            )
        raise HTTPException(status_code=500, detail="Database integrity error during manuscript catalog persistence.")
    except Exception as db_err:
        db.rollback()
        logger.error("Database error during manuscript catalog persistence: %s", db_err)
        raise HTTPException(status_code=500, detail="Failed to persist manuscript into catalog due to database error.")

    # Synchronize with FAISS vector index using existing SPECTER2 embedding pipeline
    paper_meta = {
        "id": new_paper.id,
        "paper_id": new_paper.paper_id,
        "title": new_paper.title,
        "abstract": new_paper.abstract or "",
        "authors": new_paper.authors or [],
        "venue": new_paper.venue or "",
        "year": new_paper.year,
        "doi": new_paper.doi or "",
        "source": new_paper.source,
        "citation_count": 0,
        "categories": new_paper.categories or [],
    }
    faiss_indexed = False
    try:
        faiss_index = get_faiss_index()
        faiss_index.add_papers([paper_meta])
        faiss_indexed = True
    except Exception as e:
        logger.error("Failed to synchronize FAISS index for ingested paper %s: %s", new_paper.id, e)
        faiss_indexed = False

    saved_to_lib = False
    if req.add_to_library and current_user:
        try:
            saved_entry = SavedPaper(
                user_id=current_user.username,
                paper_id=new_paper.id,
                notes=f"Ingested from {req.filename or 'uploaded manuscript'}",
                tags=["ingested", "pdf"]
            )
            db.add(saved_entry)
            db.commit()
            saved_to_lib = True
        except Exception as e:
            logger.warning("Could not auto-save ingested paper to user library: %s", e)

    if faiss_indexed:
        return PdfIngestResponse(
            status="success",
            paper_id=new_paper.paper_id,
            catalog_id=new_paper.id,
            title=new_paper.title,
            message=f"Manuscript '{new_paper.title}' successfully ingested into catalog and indexed in FAISS.",
            faiss_indexed=True,
            duplicate_detected=False,
            saved_to_library=saved_to_lib
        )
    else:
        return PdfIngestResponse(
            status="partial_success_faiss_pending",
            paper_id=new_paper.paper_id,
            catalog_id=new_paper.id,
            title=new_paper.title,
            message=f"Manuscript '{new_paper.title}' persisted to catalog (ID {new_paper.id}), but FAISS index synchronization is pending recovery.",
            faiss_indexed=False,
            duplicate_detected=False,
            saved_to_library=saved_to_lib
        )


@router.post("/upload", response_model=SearchResponse, summary="PDF Upload & Semantic Analysis")
async def upload_pdf_paper(
    file: UploadFile = File(...),
    limit: int = Form(10),
    db: Session = Depends(get_db)
):
    """
    Upload a research paper PDF.
    Enforces upload size limit, validates PDF magic bytes, extracts text using pypdf,
    and returns semantically relevant recommendations.
    """
    settings = get_settings()
    content = await _read_and_validate_pdf_upload(file, settings.MAX_UPLOAD_SIZE_BYTES)

    extracted = extract_text_from_pdf_bytes(content)
    if not extracted["success"]:
        raise HTTPException(status_code=422, detail=f"PDF extraction error: {extracted['error']}")

    raw_text = (extracted.get("raw_text") or "").strip()
    if not raw_text:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in PDF. Scanned PDFs without embedded text or OCR are not supported."
        )

    title = (extracted.get("title") or "").strip()
    abstract = (extracted.get("abstract") or "").strip()
    if not title and not abstract and len(raw_text) < 20:
        raise HTTPException(
            status_code=422,
            detail="Insufficient extractable text content to generate literature recommendations."
        )

    if not title or title == "Untitled Research Paper":
        fallback_title = file.filename.replace(".pdf", "").replace("_", " ").strip()
        title = fallback_title or "Research Manuscript"

    query_text = f"{title}. {abstract}".strip() if abstract else f"{title}. {raw_text[:500]}".strip()

    # Search for related papers using extracted content as query
    search_req = SearchQueryRequest(
        query=query_text,
        mode="pdf",
        limit=limit,
        sources=["local", "arxiv", "semanticscholar", "crossref", "dblp", "pubmed", "csir"]
    )
    return await execute_recommendation_search(db, search_req)


def _resolve_paper_by_id_or_uid(db: Session, paper_id: Union[int, str]) -> Optional[Paper]:
    """Helper to resolve paper by integer ID or string paper_id."""
    if isinstance(paper_id, int):
        return db.query(Paper).filter(Paper.id == paper_id).first()
    clean_id = str(paper_id).strip()
    if clean_id.isdigit():
        p = db.query(Paper).filter(Paper.id == int(clean_id)).first()
        if p:
            return p
    paper = db.query(Paper).filter(Paper.paper_id == clean_id).first()
    if not paper and "%" in clean_id:
        from urllib.parse import unquote
        unquoted = unquote(clean_id).strip()
        if unquoted != clean_id:
            paper = db.query(Paper).filter(Paper.paper_id == unquoted).first()
    return paper


@router.post("/compare", response_model=CompareResponse, summary="Side-by-Side Paper Comparison")
def compare_selected_papers(
    req: CompareRequest,
    db: Session = Depends(get_db)
):
    """
    Generate side-by-side comparison across 12 structured dimensions.
    Supports catalog-backed papers, transient external candidates, and mixed selections.
    """
    raw_items: List[Union[int, str, PaperBase, Dict[str, Any]]] = []
    if req.paper_ids:
        raw_items.extend(req.paper_ids)
    if req.candidates:
        raw_items.extend(req.candidates)
    if req.items:
        raw_items.extend(req.items)

    if len(raw_items) < 2:
        raise HTTPException(status_code=400, detail="Please select at least 2 papers to compare.")

    raw_identifiers: List[str] = []
    int_ids: List[int] = []
    str_ids: List[str] = []
    candidate_objects: List[Dict[str, Any]] = []

    for item in raw_items:
        if isinstance(item, int):
            int_ids.append(item)
            raw_identifiers.append(str(item))
        elif isinstance(item, str):
            clean_str = item.strip()
            if not clean_str:
                raise HTTPException(status_code=400, detail="Invalid paper identifier: empty string.")
            str_ids.append(clean_str)
            raw_identifiers.append(clean_str)
        elif isinstance(item, PaperBase):
            candidate_objects.append(item.model_dump())
            raw_identifiers.append(item.paper_id)
        elif isinstance(item, dict):
            candidate_objects.append(item)
            raw_identifiers.append(str(item.get("paper_id") or item.get("id") or item.get("title") or ""))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported comparison item type: {type(item).__name__}")

    if len(set(raw_identifiers)) < 2:
        raise HTTPException(status_code=400, detail="Please select at least 2 distinct papers to compare.")
    if len(set(raw_identifiers)) > 12:
        raise HTTPException(status_code=400, detail="Comparison limit exceeded: maximum 12 papers allowed per comparison.")

    # Query DB for integer IDs
    db_by_id = {}
    if int_ids:
        found_by_id = db.query(Paper).filter(Paper.id.in_(int_ids)).all()
        for p in found_by_id:
            db_by_id[p.id] = p

    # Query DB for string paper_ids and numeric strings
    db_by_paper_id = {}
    if str_ids:
        found_by_paper_id = db.query(Paper).filter(Paper.paper_id.in_(str_ids)).all()
        for p in found_by_paper_id:
            db_by_paper_id[p.paper_id] = p
        numeric_str_ids = [int(s) for s in str_ids if s.isdigit()]
        if numeric_str_ids:
            found_numeric = db.query(Paper).filter(Paper.id.in_(numeric_str_ids)).all()
            for p in found_numeric:
                db_by_id[p.id] = p

    # Check FAISS index metadata for unpersisted catalog metadata
    faiss_meta = {}
    try:
        from app.services.vector_index import get_faiss_index
        faiss_meta = get_faiss_index().paper_metadata
    except Exception:
        faiss_meta = {}

    resolved_by_key: Dict[str, Dict[str, Any]] = {}

    # 1. Resolve integer IDs
    for raw_int in int_ids:
        paper_obj = db_by_id.get(raw_int)
        if not paper_obj:
            raise HTTPException(status_code=404, detail=f"Paper with database ID '{raw_int}' not found.")
        canonical_key = paper_obj.paper_id or f"db:{paper_obj.id}"
        if canonical_key in resolved_by_key:
            continue
        resolved_by_key[canonical_key] = {
            "id": paper_obj.id,
            "paper_id": paper_obj.paper_id,
            "title": paper_obj.title,
            "abstract": paper_obj.abstract or "",
            "raw_text": paper_obj.raw_text or "",
            "authors": paper_obj.authors or [],
            "venue": paper_obj.venue or "",
            "year": paper_obj.year,
            "doi": paper_obj.doi,
            "url": paper_obj.url,
            "pdf_url": paper_obj.pdf_url,
            "source": paper_obj.source or "local",
            "citation_count": paper_obj.citation_count or 0,
            "categories": paper_obj.categories or []
        }

    # 2. Resolve string IDs
    for raw_str in str_ids:
        paper_obj = db_by_paper_id.get(raw_str)
        if not paper_obj and raw_str.isdigit():
            paper_obj = db_by_id.get(int(raw_str))
        if paper_obj:
            canonical_key = paper_obj.paper_id or f"db:{paper_obj.id}"
            if canonical_key in resolved_by_key:
                continue
            resolved_by_key[canonical_key] = {
                "id": paper_obj.id,
                "paper_id": paper_obj.paper_id,
                "title": paper_obj.title,
                "abstract": paper_obj.abstract or "",
                "raw_text": paper_obj.raw_text or "",
                "authors": paper_obj.authors or [],
                "venue": paper_obj.venue or "",
                "year": paper_obj.year,
                "doi": paper_obj.doi,
                "url": paper_obj.url,
                "pdf_url": paper_obj.pdf_url,
                "source": paper_obj.source or "local",
                "citation_count": paper_obj.citation_count or 0,
                "categories": paper_obj.categories or []
            }
        elif raw_str in faiss_meta:
            meta = faiss_meta[raw_str]
            canonical_key = meta.get("paper_id") or raw_str
            if canonical_key in resolved_by_key:
                continue
            resolved_by_key[canonical_key] = {
                "id": meta.get("id"),
                "paper_id": canonical_key,
                "title": meta.get("title") or "Untitled Paper",
                "abstract": meta.get("abstract") or "",
                "raw_text": "",
                "authors": meta.get("authors") or [],
                "venue": meta.get("venue") or "",
                "year": meta.get("year"),
                "doi": meta.get("doi"),
                "url": meta.get("url"),
                "pdf_url": meta.get("pdf_url"),
                "source": meta.get("source") or "external",
                "citation_count": meta.get("citation_count") or 0,
                "categories": meta.get("categories") or []
            }
        else:
            raise HTTPException(status_code=404, detail=f"Paper '{raw_str}' not found.")

    # 3. Resolve candidate objects (transient external papers or candidate dictionaries)
    for cand in candidate_objects:
        cand_pid = str(cand.get("paper_id") or "").strip()
        cand_title = str(cand.get("title") or "Untitled Paper").strip()
        if not cand_pid:
            if cand.get("doi"):
                cand_pid = f"doi:{str(cand.get('doi')).strip()}"
            else:
                raise HTTPException(status_code=400, detail="External candidate is missing paper_id identifier.")

        # Validate URL schemes if provided
        for u in [cand.get("url"), cand.get("pdf_url")]:
            if u:
                parsed_u = urlparse(str(u).strip())
                if parsed_u.scheme.lower() not in ("http", "https"):
                    raise HTTPException(status_code=400, detail=f"Unsafe URL scheme '{parsed_u.scheme}' in candidate.")

        canonical_key = cand_pid
        if canonical_key in resolved_by_key:
            continue

        # Check if this candidate corresponds to an existing catalog row in DB
        paper_obj = None
        cand_id_val = cand.get("id")
        if cand_id_val is not None and isinstance(cand_id_val, int):
            paper_obj = db_by_id.get(cand_id_val) or db.query(Paper).filter(Paper.id == cand_id_val).first()
        elif cand_pid in db_by_paper_id:
            paper_obj = db_by_paper_id[cand_pid]
        else:
            paper_obj = db.query(Paper).filter(Paper.paper_id == cand_pid).first()
            if not paper_obj and cand.get("doi"):
                paper_obj = db.query(Paper).filter(Paper.doi == str(cand.get("doi")).strip()).first()

        if paper_obj:
            resolved_by_key[canonical_key] = {
                "id": paper_obj.id,
                "paper_id": paper_obj.paper_id or cand_pid,
                "title": paper_obj.title,
                "abstract": paper_obj.abstract or str(cand.get("abstract") or ""),
                "raw_text": paper_obj.raw_text or str(cand.get("raw_text") or ""),
                "authors": paper_obj.authors or cand.get("authors") or [],
                "venue": paper_obj.venue or cand.get("venue") or "",
                "year": paper_obj.year or cand.get("year"),
                "doi": paper_obj.doi or cand.get("doi"),
                "url": paper_obj.url or cand.get("url"),
                "pdf_url": paper_obj.pdf_url or cand.get("pdf_url"),
                "source": paper_obj.source or cand.get("source") or "local",
                "citation_count": paper_obj.citation_count or cand.get("citation_count") or 0,
                "categories": paper_obj.categories or cand.get("categories") or []
            }
        else:
            resolved_by_key[canonical_key] = {
                "id": None,  # Transient external candidate
                "paper_id": cand_pid,
                "title": cand_title[:500],
                "abstract": str(cand.get("abstract") or "")[:50000],
                "raw_text": str(cand.get("raw_text") or "")[:500000],
                "authors": cand.get("authors") or [],
                "venue": str(cand.get("venue") or "")[:255] if cand.get("venue") else "",
                "year": cand.get("year"),
                "doi": str(cand.get("doi") or "")[:255] if cand.get("doi") else None,
                "url": str(cand.get("url") or "")[:500] if cand.get("url") else None,
                "pdf_url": str(cand.get("pdf_url") or "")[:500] if cand.get("pdf_url") else None,
                "source": cand.get("source") or "external",
                "citation_count": cand.get("citation_count") or 0,
                "categories": cand.get("categories") or []
            }

    if len(resolved_by_key) < 2:
        raise HTTPException(status_code=400, detail="Please select at least 2 distinct papers to compare.")
    if len(resolved_by_key) > 12:
        raise HTTPException(status_code=400, detail="Comparison limit exceeded: maximum 12 papers allowed per comparison.")

    return compare_papers(list(resolved_by_key.values()), db=db)


@router.get("/{paper_id:path}/summary", response_model=SummaryResponse, summary="AI-Generated Paper Summary")
def get_paper_summary(
    paper_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate structured academic summary: Problem Statement, Methodology, Key Findings, Limitations.
    """
    paper = _resolve_paper_by_id_or_uid(db, paper_id)
    if not paper:
        faiss_meta = {}
        try:
            from app.services.vector_index import get_faiss_index
            faiss_meta = get_faiss_index().paper_metadata
        except Exception:
            faiss_meta = {}
        clean_pid = str(paper_id).strip()
        from urllib.parse import unquote
        matched_key = clean_pid if clean_pid in faiss_meta else (unquote(clean_pid) if "%" in clean_pid and unquote(clean_pid) in faiss_meta else None)
        if matched_key:
            meta = faiss_meta[matched_key]
            return generate_paper_summary({
                "id": meta.get("id"),
                "paper_id": meta.get("paper_id") or matched_key,
                "title": meta.get("title") or "Untitled Paper",
                "abstract": meta.get("abstract") or "",
                "venue": meta.get("venue"),
                "year": meta.get("year"),
                "citation_count": meta.get("citation_count") or 0,
            })
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found.")

    p_dict = {
        "id": paper.id,
        "paper_id": paper.paper_id,
        "title": paper.title,
        "abstract": paper.abstract,
        "venue": paper.venue,
        "year": paper.year,
        "citation_count": paper.citation_count
    }
    return generate_paper_summary(p_dict)


@router.post("/summary", response_model=SummaryResponse, summary="Structured Paper Summary for Candidate")
def post_paper_summary(
    req: PaperSummaryRequest,
    db: Session = Depends(get_db)
):
    """
    Generate structured academic summary for either a catalog-backed paper or a transient candidate without side-effects.
    """
    candidate_dict = None
    if req.candidate:
        candidate_dict = req.candidate.model_dump()
    elif req.title:
        candidate_dict = {
            "paper_id": req.paper_id or "external:transient",
            "title": req.title.strip()[:500],
            "abstract": (req.abstract or "").strip()[:50000],
            "authors": req.authors or [],
            "venue": (req.venue or "").strip()[:255] if req.venue else "",
            "year": req.year,
            "citation_count": req.citation_count or 0,
            "source": req.source or "external"
        }
    elif req.paper_id:
        paper = _resolve_paper_by_id_or_uid(db, req.paper_id)
        if paper:
            candidate_dict = {
                "id": paper.id,
                "paper_id": paper.paper_id,
                "title": paper.title,
                "abstract": paper.abstract or "",
                "venue": paper.venue,
                "year": paper.year,
                "citation_count": paper.citation_count or 0,
                "source": paper.source or "local"
            }
        else:
            faiss_meta = {}
            try:
                from app.services.vector_index import get_faiss_index
                faiss_meta = get_faiss_index().paper_metadata
            except Exception:
                faiss_meta = {}
            str_pid = str(req.paper_id).strip()
            if str_pid in faiss_meta:
                meta = faiss_meta[str_pid]
                candidate_dict = {
                    "id": meta.get("id"),
                    "paper_id": meta.get("paper_id") or str_pid,
                    "title": meta.get("title") or "Untitled Paper",
                    "abstract": meta.get("abstract") or "",
                    "venue": meta.get("venue"),
                    "year": meta.get("year"),
                    "citation_count": meta.get("citation_count") or 0,
                    "source": meta.get("source") or "external"
                }
            else:
                raise HTTPException(status_code=404, detail=f"Paper '{req.paper_id}' not found.")
    else:
        raise HTTPException(status_code=400, detail="Either paper_id or candidate details must be provided.")

    abstract = (candidate_dict.get("abstract") or "").strip()
    title = candidate_dict.get("title") or "Untitled Paper"
    venue = candidate_dict.get("venue")
    year = candidate_dict.get("year")
    source = candidate_dict.get("source", "external source")

    if not abstract or len(abstract) < 20:
        return SummaryResponse(
            paper_id=str(candidate_dict.get("paper_id") or ""),
            title=title,
            executive_summary=(
                f"\"{title}\" ({venue or 'Academic publication'}, {year or 'recent'}) was retrieved from {source}, "
                "but insufficient abstract content was provided by the external source to generate a detailed academic synthesis."
            ),
            problem_statement="Insufficient source content provided to extract problem statement.",
            methodology="Insufficient source content provided to extract methodology.",
            key_findings="Insufficient source content provided to extract key findings.",
            limitations="Insufficient source content provided to evaluate limitations.",
            suggested_reading_order=[
                "1. Consult full manuscript if available at publication URL",
                "2. Inspect publication metadata and author profile"
            ]
        )

    return generate_paper_summary(candidate_dict)


@router.get("/saved", response_model=List[SavedPaperResponse], summary="Get Saved Papers Library")
def get_saved_papers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all papers saved by the authenticated researcher."""
    saved_list = db.query(SavedPaper).filter(
        SavedPaper.user_id == current_user.username
    ).order_by(SavedPaper.saved_at.desc()).all()
    return saved_list


@router.post("/save", response_model=SavedPaperResponse, summary="Save Paper to Library")
def save_paper_to_library(
    req: SavePaperRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bookmark paper and add to researcher's saved library."""
    paper = None
    if req.candidate:
        cand = req.candidate
        cand_pid = str(cand.paper_id or "").strip()
        if not cand_pid and cand.doi:
            cand_pid = f"doi:{str(cand.doi).strip()}"
        if not cand_pid:
            raise HTTPException(status_code=400, detail="External candidate is missing a valid paper_id or DOI.")

        # Check if paper with paper_id or DOI already exists in DB
        paper = db.query(Paper).filter(Paper.paper_id == cand_pid).first()
        if not paper and cand.doi:
            paper = db.query(Paper).filter(Paper.doi == str(cand.doi).strip()).first()

        if not paper:
            # Explicit user save action: persist candidate to catalog
            paper = Paper(
                paper_id=cand_pid,
                title=cand.title.strip()[:500],
                abstract=(cand.abstract or "").strip()[:50000] if cand.abstract else None,
                authors=cand.authors or [],
                venue=(cand.venue or "").strip()[:255] if cand.venue else None,
                year=cand.year,
                doi=str(cand.doi).strip()[:255] if cand.doi else None,
                url=str(cand.url).strip()[:500] if cand.url else None,
                pdf_url=str(cand.pdf_url).strip()[:500] if cand.pdf_url else None,
                source=cand.source or "external",
                citation_count=cand.citation_count or 0,
                categories=cand.categories or []
            )
            try:
                db.add(paper)
                db.commit()
                db.refresh(paper)
            except IntegrityError:
                db.rollback()
                paper = db.query(Paper).filter(Paper.paper_id == cand_pid).first()
                if not paper and cand.doi:
                    paper = db.query(Paper).filter(Paper.doi == str(cand.doi).strip()).first()
                if not paper:
                    raise HTTPException(status_code=500, detail="Failed to persist candidate due to database concurrency conflict.")
    elif req.paper_id is not None:
        paper = _resolve_paper_by_id_or_uid(db, req.paper_id)
        if not paper:
            raise HTTPException(
                status_code=404,
                detail=f"Paper with ID '{req.paper_id}' not found in catalog. To bookmark an external paper, provide its candidate payload."
            )
    else:
        raise HTTPException(status_code=400, detail="Either paper_id or candidate payload must be provided.")

    if not paper or not paper.id:
        raise HTTPException(status_code=404, detail="Paper record could not be resolved.")

    existing = db.query(SavedPaper).filter(
        SavedPaper.user_id == current_user.username,
        SavedPaper.paper_id == paper.id
    ).first()

    if existing:
        if req.notes is not None:
            existing.notes = req.notes
        if req.tags is not None:
            existing.tags = req.tags
        db.commit()
        db.refresh(existing)
        return existing

    saved = SavedPaper(
        user_id=current_user.username,
        paper_id=paper.id,
        notes=req.notes or "",
        tags=req.tags or []
    )
    try:
        db.add(saved)
        db.commit()
        db.refresh(saved)
    except IntegrityError:
        db.rollback()
        existing = db.query(SavedPaper).filter(
            SavedPaper.user_id == current_user.username,
            SavedPaper.paper_id == paper.id
        ).first()
        if existing:
            return existing
        raise HTTPException(status_code=500, detail="Failed to save paper bookmark due to concurrent request.")
    return saved


@router.delete("/saved/{saved_id}", summary="Remove Paper from Library")
def delete_saved_paper(
    saved_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove paper from saved library, strictly scoped to current user."""
    saved = db.query(SavedPaper).filter(
        SavedPaper.id == saved_id,
        SavedPaper.user_id == current_user.username
    ).first()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved paper entry not found.")
    db.delete(saved)
    db.commit()
    return {"status": "success", "message": "Paper removed from library."}


@router.get("/driut/alerts", response_model=List[DRIUTAlertResponse], summary="Get DRIUT Research Update Alerts")
def get_driut_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve all Dynamic Research Impact Update Tracker alerts for the user.
    Classified into Extension, Improvement, Challenge, Reproduction, Alternative, or Potential Replacement.
    """
    alerts = db.query(DRIUTAlert).filter(
        DRIUTAlert.user_id == current_user.username
    ).order_by(DRIUTAlert.created_at.desc()).all()
    return alerts


@router.get("/driut/status", response_model=DRIUTStatusResponse, summary="Get DRIUT Monitoring Status")
def get_driut_status(
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve real-time background scheduler state, monitoring interval, and academic provider health.
    """
    return driut_scheduler.get_status()


@router.post("/driut/scan", response_model=DRIUTScanResponse, summary="Trigger DRIUT Scan")
async def trigger_driut_scan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually scan literature against researcher's saved papers.
    Identifies impact relationships and generates new alerts strictly for the authenticated user.
    """
    settings = get_settings()
    res = await driut_scheduler.run_scan_job(
        user_id=current_user.username,
        query_academic=settings.DRIUT_QUERY_ACADEMIC_SOURCES
    )
    all_alerts = db.query(DRIUTAlert).filter(
        DRIUTAlert.user_id == current_user.username
    ).order_by(DRIUTAlert.created_at.desc()).all()

    eval_count = res.get("papers_evaluated", 0)
    new_count = res.get("new_alerts_created", 0)

    return DRIUTScanResponse(
        message=f"DRIUT scan completed successfully. Evaluated {eval_count} papers against saved library.",
        new_alerts_count=new_count,
        alerts=all_alerts
    )


@router.patch("/driut/alerts/{alert_id}/read", summary="Mark DRIUT Alert as Read")
def mark_alert_as_read(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark an alert as read, strictly scoped to current user ownership."""
    alert = db.query(DRIUTAlert).filter(
        DRIUTAlert.id == alert_id,
        DRIUTAlert.user_id == current_user.username
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    alert.is_read = True
    db.commit()
    return {"status": "success", "alert_id": alert_id, "is_read": True}


# ---------------------------------------------------------------------------
# Vector Index Maintenance & Administrative Synchronization (TASK-07D)
# ---------------------------------------------------------------------------

@router.get("/index-status", summary="Get Vector Index Consistency Status")
def get_vector_index_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve synchronization metrics comparing PostgreSQL paper database records
    with the active FAISS vector index.
    """
    return get_index_consistency_status(session=db)



# ---------------------------------------------------------------------------
# Research Evidence Grounding Endpoints (TASK-13)
# ---------------------------------------------------------------------------

@router.post("/evidence", response_model=PaperEvidenceResponse, summary="Retrieve Grounded Evidence for Candidate")
def post_paper_evidence(
    req: TransientEvidenceRequest,
    db: Session = Depends(get_db)
):
    """
    Retrieve grounded research evidence for either a catalog paper or a transient candidate without database writes.
    """
    candidate_dict = None
    if req.candidate:
        candidate_dict = req.candidate.model_dump()
    elif req.title:
        candidate_dict = {
            "paper_id": req.paper_id or "external:transient",
            "title": req.title,
            "abstract": req.abstract or "",
            "raw_text": req.raw_text or "",
            "source": req.source or "external"
        }
    elif req.paper_id:
        paper = _resolve_paper_by_id_or_uid(db, req.paper_id)
        if paper:
            return get_paper_evidence(db=db, paper=paper, category=req.category)
        faiss_meta = {}
        try:
            from app.services.vector_index import get_faiss_index
            faiss_meta = get_faiss_index().paper_metadata
        except Exception:
            faiss_meta = {}
        str_pid = str(req.paper_id).strip()
        if str_pid in faiss_meta:
            meta = faiss_meta[str_pid]
            candidate_dict = {
                "paper_id": str_pid,
                "title": meta.get("title", "Untitled"),
                "abstract": meta.get("abstract", ""),
                "raw_text": "",
                "source": meta.get("source", "external")
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paper with identifier '{req.paper_id}' not found."
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either paper_id or candidate details must be provided."
        )

    raw_text = (candidate_dict.get("raw_text") or "").strip()
    abstract = (candidate_dict.get("abstract") or "").strip()

    source_text = raw_text if len(raw_text) >= 100 else abstract
    source_type = "full_text" if len(raw_text) >= 100 else ("abstract" if source_text else "unavailable")

    if not source_text or len(source_text) < 20:
        return PaperEvidenceResponse(
            paper_id=str(candidate_dict.get("paper_id") or "external:transient"),
            paper_title=candidate_dict.get("title", "Untitled"),
            status="insufficient_text",
            source_type=source_type,
            evidence_count=0,
            categories_present=[],
            missing_categories=list(ALL_EVIDENCE_CATEGORIES),
            evidence=[],
            verification_summary=EvidenceVerificationSummary(
                total_evidence=0,
                verified_count=0,
                is_stale=False,
                source_type=source_type,
                char_offsets_valid=True,
                nonempty_passages=True,
                verification_message="Insufficient source content provided by external provider to extract grounded evidence."
            )
        )

    raw_items, missing_categories = extract_evidence_from_text(source_text, source_type=source_type, max_items_per_category=2)
    if req.category and req.category in ALL_EVIDENCE_CATEGORIES:
        raw_items = [i for i in raw_items if i["category"] == req.category]

    response_items: List[EvidenceItemResponse] = []
    present_categories: set[str] = set()
    all_offsets_valid = True

    for idx, item in enumerate(raw_items):
        start = item["char_start"]
        end = item["char_end"]
        passage = item["source_passage"]
        if start is not None and end is not None and source_text[start:end] == passage:
            is_ver = True
        else:
            all_offsets_valid = False
            is_ver = False

        response_items.append(EvidenceItemResponse(
            id=idx + 1,
            paper_id=0,
            category=item["category"],
            category_label=CATEGORY_LABELS.get(item["category"], item["category"].title()),
            claim=item["claim"],
            source_passage=passage,
            char_start=start,
            char_end=end,
            page_number=item.get("page_number"),
            section_name=item.get("section_name"),
            source_type=source_type,
            extraction_method=item.get("extraction_method", "rule_pattern"),
            confidence_score=item.get("confidence_score", 0.8),
            is_verified=is_ver,
            verification_notes="Verified in-memory against provided source text." if is_ver else "Span mismatch",
            source_hash=compute_source_hash(source_text),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ))
        present_categories.add(item["category"])

    status_val = "supported" if response_items else "no_evidence_found"
    ver_msg = (
        f"Retrieved {len(response_items)} grounded evidence items verified against {source_type} (in-memory, unpersisted)."
        if response_items
        else f"Text was inspected ({len(source_text)} chars), but no explicit scientific evidence patterns were matched."
    )

    return PaperEvidenceResponse(
        paper_id=str(candidate_dict.get("paper_id") or "external:transient"),
        paper_title=candidate_dict.get("title", "Untitled"),
        status=status_val,
        source_type=source_type,
        evidence_count=len(response_items),
        categories_present=sorted(list(present_categories)),
        missing_categories=missing_categories,
        evidence=response_items,
        verification_summary=EvidenceVerificationSummary(
            total_evidence=len(response_items),
            verified_count=sum(1 for i in response_items if i.is_verified),
            is_stale=False,
            source_type=source_type,
            char_offsets_valid=all_offsets_valid,
            nonempty_passages=True,
            verification_message=ver_msg
        )
    )


@router.post("/{paper_id:path}/evidence/extract", response_model=PaperEvidenceResponse, summary="Extract or Refresh Paper Evidence")
def extract_paper_evidence_endpoint(
    paper_id: str,
    req: Optional[EvidenceExtractionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Extract or refresh grounded research evidence for a paper.
    Requires authentication. Idempotent: re-extracts cleanly if force=True or text has changed.
    """
    paper = _resolve_paper_by_id_or_uid(db, paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with identifier '{paper_id}' not found."
        )

    force = req.force if req else False
    return extract_and_persist_paper_evidence(db=db, paper=paper, force=force)


@router.get("/{paper_id:path}/evidence/verify", summary="Verify Paper Evidence Integrity")
def verify_paper_evidence_endpoint(
    paper_id: str,
    db: Session = Depends(get_db)
):
    """
    Perform a complete source-span and provenance integrity audit on stored evidence for a paper.
    Verifies that all stored spans match the original source text and flags any stale or invalid records.
    """
    paper = _resolve_paper_by_id_or_uid(db, paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with identifier '{paper_id}' not found."
        )

    records = db.query(PaperEvidence).filter(PaperEvidence.paper_id == paper.id).all()
    results = []
    all_valid = True

    for r in records:
        v = verify_evidence_record(r, paper)
        if not v.get("is_valid", False):
            all_valid = False
        results.append({
            "evidence_id": r.id,
            "category": r.category,
            "claim": r.claim,
            "source_passage": r.source_passage,
            "char_start": r.char_start,
            "char_end": r.char_end,
            "source_type": r.source_type,
            "verification": v
        })

    return {
        "paper_id": paper.paper_id,
        "paper_title": paper.title,
        "total_records": len(records),
        "all_valid": all_valid,
        "audit_results": results
    }


@router.get("/{paper_id:path}/evidence", response_model=PaperEvidenceResponse, summary="Retrieve Grounded Paper Evidence")
def get_paper_evidence_endpoint(
    paper_id: str,
    category: Optional[str] = Query(default=None, description="Filter evidence by category"),
    db: Session = Depends(get_db)
):
    """
    Retrieve grounded research evidence for a paper, with optional category filtering.
    Reports extraction status, provenance, and source verification details.
    """
    if category and category not in ALL_EVIDENCE_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid evidence category '{category}'. Valid categories: {ALL_EVIDENCE_CATEGORIES}"
        )

    paper = _resolve_paper_by_id_or_uid(db, paper_id)
    if not paper:
        faiss_meta = {}
        try:
            from app.services.vector_index import get_faiss_index
            faiss_meta = get_faiss_index().paper_metadata
        except Exception:
            faiss_meta = {}
        clean_pid = str(paper_id).strip()
        from urllib.parse import unquote
        matched_key = clean_pid if clean_pid in faiss_meta else (unquote(clean_pid) if "%" in clean_pid and unquote(clean_pid) in faiss_meta else None)
        if matched_key:
            meta = faiss_meta[matched_key]
            req_transient = TransientEvidenceRequest(
                paper_id=matched_key,
                title=meta.get("title", "Untitled"),
                abstract=meta.get("abstract", ""),
                category=category
            )
            return post_paper_evidence(req_transient, db=db)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Paper with identifier '{paper_id}' not found."
        )

    return get_paper_evidence(db=db, paper=paper, category=category)


