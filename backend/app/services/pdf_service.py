"""
PDF extraction service using pypdf.
Extracts title, abstract, authors, publication year, DOI, venue, keywords, and text content
from uploaded academic PDF documents with robust validation and security protections.
"""
import io
import re
from typing import Dict, Any, Optional, List
from pypdf import PdfReader
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Extract text, page count, and structural metadata from PDF bytes.
    Validates encryption, extracts metadata (title, abstract, authors, year, DOI, venue, keywords),
    and enforces safe processing boundaries.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))

        # 1. Encryption and Password Protection check
        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt("")
                if decrypted == 0:
                    return {
                        "title": "",
                        "abstract": "",
                        "authors": [],
                        "year": None,
                        "doi": None,
                        "venue": None,
                        "keywords": [],
                        "raw_text": "",
                        "page_count": 0,
                        "success": False,
                        "error": "Password-protected or encrypted PDF files cannot be processed."
                    }
            except Exception as e:
                return {
                    "title": "",
                    "abstract": "",
                    "authors": [],
                    "year": None,
                    "doi": None,
                    "venue": None,
                    "keywords": [],
                    "raw_text": "",
                    "page_count": 0,
                    "success": False,
                    "error": f"Failed to decrypt PDF document: {e}"
                }

        num_pages = len(reader.pages)
        if num_pages == 0:
            return {
                "title": "",
                "abstract": "",
                "authors": [],
                "year": None,
                "doi": None,
                "venue": None,
                "keywords": [],
                "raw_text": "",
                "page_count": 0,
                "success": False,
                "error": "Uploaded PDF contains 0 pages."
            }

        full_text_list = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            full_text_list.append(page_text)

        full_text = "\n\n".join(full_text_list).strip()
        first_page_text = full_text_list[0] if full_text_list else ""

        # Check for scanned or blank document (no extractable text)
        if len(full_text.strip()) == 0:
            return {
                "title": "",
                "abstract": "",
                "authors": [],
                "year": None,
                "doi": None,
                "venue": None,
                "keywords": [],
                "raw_text": "",
                "page_count": num_pages,
                "success": False,
                "error": "No extractable text found in PDF. Scanned PDFs without embedded text or OCR are not supported."
            }

        # Safe bounding: cap raw text at 500,000 characters to prevent memory exhaustion
        if len(full_text) > 500000:
            full_text = full_text[:500000]

        pdf_meta = {}
        try:
            if reader.metadata:
                pdf_meta = dict(reader.metadata)
        except Exception:
            pdf_meta = {}

        # Heuristic metadata extraction
        title = extract_heuristic_title(first_page_text, pdf_meta)
        abstract = extract_heuristic_abstract(full_text)
        keywords = extract_heuristic_keywords(full_text)
        authors = extract_heuristic_authors(first_page_text, title, pdf_meta)
        year = extract_heuristic_year(full_text, pdf_meta)
        doi = extract_heuristic_doi(full_text)
        venue = extract_heuristic_venue(first_page_text)

        return {
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "year": year,
            "doi": doi,
            "venue": venue,
            "keywords": keywords,
            "raw_text": full_text,
            "page_count": num_pages,
            "success": True,
            "error": None
        }
    except Exception as e:
        logger.error("Failed to extract text from PDF: %s", e)
        return {
            "title": "",
            "abstract": "",
            "authors": [],
            "year": None,
            "doi": None,
            "venue": None,
            "keywords": [],
            "raw_text": "",
            "page_count": 0,
            "success": False,
            "error": str(e)
        }


def extract_heuristic_title(first_page_text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Extract candidate title from first page or metadata."""
    lines = [l.strip() for l in first_page_text.splitlines() if l.strip()]
    candidate_lines = []
    for line in lines[:8]:
        # Ignore common preprint headers or arXiv stamps
        if re.search(r"arxiv|conference|proceedings|journal|vol\.|doi|issn", line, re.I):
            continue
        # Stop if we hit abstract or author indicators
        if re.search(r"^(abstract|keywords|by|author)", line, re.I):
            break
        candidate_lines.append(line)
        if len(" ".join(candidate_lines)) > 60:
            break
    title = " ".join(candidate_lines).strip()
    if title:
        return title[:500]

    # Fallback to metadata if clean
    if metadata:
        meta_title = metadata.get("/Title") or metadata.get("Title") or ""
        if isinstance(meta_title, str) and meta_title.strip() and not re.search(r"\.pdf|untitled|microsoft|latex", meta_title, re.I):
            return meta_title.strip()[:500]

    return "Untitled Research Paper"


def extract_heuristic_abstract(text: str) -> str:
    """Extract candidate abstract using regex boundaries."""
    match = re.search(r"abstract[\s:—–-]*\n?(.*?)(?=\n\s*(?:keywords|index terms|1\.?\s*introduction|1\s+[A-Z]))", text, re.I | re.DOTALL)
    if match:
        clean_abs = " ".join(match.group(1).split())
        return clean_abs[:3000]
    # Fallback to first 800 characters if no clean abstract header found
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 40]
    return " ".join(lines[:4])[:1000]


def extract_heuristic_keywords(text: str) -> List[str]:
    """Extract keywords if explicitly listed in text."""
    match = re.search(r"(?:keywords|index terms)[\s:—–-]*\n?(.*?)(?=\n\s*(?:1\.?\s*introduction|1\s+[A-Z]|\n\n))", text, re.I | re.DOTALL)
    if match:
        raw_kw = match.group(1).replace(";", ",").replace("—", ",")
        return [k.strip() for k in raw_kw.split(",") if k.strip() and len(k.strip()) < 50][:10]
    return []


def extract_heuristic_doi(text: str) -> Optional[str]:
    """Extract candidate DOI from text using standard DOI regex."""
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", text)
    if match:
        doi = match.group(0).rstrip(".,;)")
        return doi[:100]
    return None


def extract_heuristic_year(text: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[int]:
    """Extract candidate publication year from metadata or first page text."""
    if metadata:
        creation = metadata.get("/CreationDate") or metadata.get("CreationDate") or ""
        m_date = re.search(r"D:?(19[89]\d|20[0-2]\d)", str(creation))
        if m_date:
            return int(m_date.group(1))

    # Search in text header
    m_year = re.search(r"\b(20[0-2]\d|19[89]\d)\b", text[:3000])
    if m_year:
        return int(m_year.group(1))
    return None


def extract_heuristic_authors(first_page_text: str, title: str, metadata: Optional[Dict[str, Any]] = None) -> List[str]:
    """Extract candidate author names from PDF metadata or first page text."""
    authors: List[str] = []
    # 1. Try PDF metadata
    if metadata:
        author_meta = metadata.get("/Author") or metadata.get("Author") or ""
        if isinstance(author_meta, str) and author_meta.strip() and not re.search(r"latex|microsoft|acrobat|writer|word|unknown", author_meta, re.I):
            raw_authors = re.split(r"[,;]| and ", author_meta)
            for a in raw_authors:
                cleaned = a.strip()
                if 2 < len(cleaned) < 50 and not any(ch in cleaned for ch in "@{}<>"):
                    authors.append(cleaned)
            if authors:
                return authors[:10]

    # 2. Heuristic from first page text
    lines = [l.strip() for l in first_page_text.splitlines() if l.strip()]
    in_author_zone = False
    skip_keywords = {"abstract", "keywords", "university", "department", "dept", "laboratory", "institute", "school", "college", "email", "@", "usa", "uk", "china", "india", "germany", "japan"}

    candidate_lines = []
    norm_title = re.sub(r"[^\w\s]", "", title.lower())
    for line in lines:
        norm_line = re.sub(r"[^\w\s]", "", line.lower())
        if not in_author_zone:
            if norm_title and (norm_title in norm_line or norm_line in norm_title):
                in_author_zone = True
                continue
            elif len(candidate_lines) == 0 and len(line) > 10:
                in_author_zone = True

        if in_author_zone:
            if re.search(r"^(abstract|keywords|1\.?\s*introduction)", line, re.I):
                break
            if any(k in line.lower() for k in skip_keywords):
                continue
            if len(line) < 80:
                candidate_lines.append(line)
            if len(candidate_lines) >= 3:
                break

    for line in candidate_lines:
        parts = re.split(r"[,;]| and ", line)
        for p in parts:
            p_clean = re.sub(r"[\d\*†‡§\(\)]", "", p).strip()
            if 2 < len(p_clean) < 40 and not any(ch in p_clean for ch in "@{}<>"):
                if re.match(r"^[A-Z][a-zA-Z\.\s\-']+$", p_clean) and p_clean not in authors:
                    authors.append(p_clean)

    return authors[:8]


def extract_heuristic_venue(first_page_text: str) -> Optional[str]:
    """Detect common conference or journal venue indicators from first page."""
    venue_patterns = [
        r"(arXiv:\d+\.\d+(?:v\d+)?)",
        r"(IEEE\s+[A-Za-z\s]+(?:Transactions|Conference|Letters)?)",
        r"(ACM\s+[A-Za-z\s]+(?:Transactions|Conference)?)",
        r"(NeurIPS\s*\d{4})",
        r"(ICLR\s*\d{4})",
        r"(ICML\s*\d{4})",
        r"(ACL\s*\d{4})",
        r"(CVPR\s*\d{4})",
        r"(Nature\s+[A-Za-z\s]*)",
        r"(Science\s+[A-Za-z\s]*)"
    ]
    for pat in venue_patterns:
        m = re.search(pat, first_page_text, re.I)
        if m:
            return m.group(1).strip()[:100]
    return None
