"""
Duplicate detection service for academic research papers.
Eliminates duplicates across arXiv, Semantic Scholar, Crossref, CORE, DBLP, and local papers.
"""
import re
from typing import List, Dict, Any, Tuple


def normalize_title(title: str) -> str:
    """Normalize paper title for exact or fuzzy comparison."""
    if not title:
        return ""
    # Lowercase, remove all punctuation and non-alphanumeric characters, collapse whitespace
    cleaned = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(cleaned.split())


def compute_title_jaccard_similarity(t1: str, t2: str) -> float:
    """Token-based Jaccard similarity between two normalized titles."""
    words1 = set(normalize_title(t1).split())
    words2 = set(normalize_title(t2).split())
    if not words1 or not words2:
        return 0.0
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    return intersection / union if union > 0 else 0.0


def is_duplicate(p1: Dict[str, Any], p2: Dict[str, Any], similarity_threshold: float = 0.85) -> Tuple[bool, str]:
    """
    Check if two papers are duplicates based on:
    1. Matching DOI
    2. Matching Paper ID / arXiv ID
    3. High title token similarity
    """
    # 1. DOI matching
    doi1 = (p1.get("doi") or "").strip().lower()
    doi2 = (p2.get("doi") or "").strip().lower()
    if doi1 and doi2 and doi1 == doi2:
        return True, f"Matched DOI: {doi1}"

    # 2. Paper ID matching
    id1 = (p1.get("paper_id") or "").strip().lower()
    id2 = (p2.get("paper_id") or "").strip().lower()
    if id1 and id2 and id1 == id2:
        return True, f"Matched ID: {id1}"

    # 3. Normalized Title matching
    t1 = p1.get("title", "")
    t2 = p2.get("title", "")
    norm1 = normalize_title(t1)
    norm2 = normalize_title(t2)

    if norm1 and norm2 and norm1 == norm2:
        return True, "Exact normalized title match"

    sim = compute_title_jaccard_similarity(t1, t2)
    if sim >= similarity_threshold:
        return True, f"High title similarity ({sim:.2f})"

    return False, ""


def deduplicate_papers(papers: List[Dict[str, Any]], similarity_threshold: float = 0.85) -> List[Dict[str, Any]]:
    """
    Filter out duplicate research papers from a combined list,
    preserving the record with the most complete metadata (abstract, citations, DOI).
    """
    unique_papers: List[Dict[str, Any]] = []

    for paper in papers:
        dup_found = False
        for i, existing in enumerate(unique_papers):
            is_dup, reason = is_duplicate(paper, existing, similarity_threshold)
            if is_dup:
                dup_found = True
                if len(paper.get("abstract") or "") > len(existing.get("abstract") or ""):
                    existing["abstract"] = paper["abstract"]
                if (paper.get("citation_count") or 0) > (existing.get("citation_count") or 0):
                    existing["citation_count"] = paper["citation_count"]
                if not existing.get("pdf_url") and paper.get("pdf_url"):
                    existing["pdf_url"] = paper["pdf_url"]
                if not existing.get("doi") and paper.get("doi"):
                    existing["doi"] = paper["doi"]
                if not existing.get("id") and paper.get("id"):
                    existing["id"] = paper["id"]
                if not existing.get("url") and paper.get("url"):
                    existing["url"] = paper["url"]
                if existing.get("year") is None and paper.get("year") is not None:
                    existing["year"] = paper["year"]
                if (not existing.get("authors") or len(existing.get("authors", [])) == 0) and paper.get("authors"):
                    existing["authors"] = paper["authors"]
                if (not existing.get("venue") or existing.get("venue") in ["Crossref", "DBLP"]) and paper.get("venue") and paper.get("venue") not in ["Crossref", "DBLP"]:
                    existing["venue"] = paper["venue"]
                break

        if not dup_found:
            unique_papers.append(paper)

    return unique_papers
