"""
FastAPI endpoints for Research Evolution Timeline, Paper Relationship Graph,
and Candidate Research-Gap Explorer.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research import (
    TimelineResponse,
    RelationshipGraphResponse,
    GapExplorationRequest,
    GapExplorationResponse,
    ResearchAssistantRequest,
    ResearchAssistantResponse,
)
from app.services.evolution_service import (
    build_research_timeline,
    build_relationship_graph,
    explore_candidate_gaps,
)
from app.services.assistant_service import (
    answer_research_question,
)
from app.services.ai_provider import (
    AIProviderStatus,
    get_ai_coordinator,
)

router = APIRouter()


@router.get(
    "/timeline",
    response_model=TimelineResponse,
    summary="Research Evolution Timeline",
    description=(
        "Retrieve an evidence-grounded chronological research timeline. "
        "Separates publication dates from ingestion dates, transparently isolates undated papers, "
        "and links claims (methods, datasets, findings, limitations) to verified source passages."
    )
)
def get_research_timeline(
    topic: Optional[str] = Query(None, description="Topic or keyword filter for research timeline"),
    start_year: Optional[int] = Query(None, ge=1900, le=2035, description="Start publication year filter"),
    end_year: Optional[int] = Query(None, ge=1900, le=2035, description="End publication year filter"),
    limit: int = Query(50, ge=1, le=100, description="Maximum papers to include in timeline"),
    db: Session = Depends(get_db)
) -> TimelineResponse:
    return build_research_timeline(
        db=db,
        topic=topic,
        start_year=start_year,
        end_year=end_year,
        limit=limit
    )


@router.get(
    "/graph",
    response_model=RelationshipGraphResponse,
    summary="Research Relationship Graph",
    description=(
        "Retrieve an interactive inter-paper relationship graph. "
        "Explicitly distinguishes author-stated relationships from system inferences, "
        "and semantic proximity from proven scientific agreement. Zero artificial citation links."
    )
)
def get_relationship_graph(
    topic: Optional[str] = Query(None, description="Topic or keyword filter for relationship graph"),
    start_year: Optional[int] = Query(None, ge=1900, le=2035, description="Start publication year filter"),
    end_year: Optional[int] = Query(None, ge=1900, le=2035, description="End publication year filter"),
    min_similarity: float = Query(0.45, ge=0.0, le=1.0, description="Minimum cosine similarity threshold for edges"),
    max_nodes: int = Query(25, ge=2, le=50, description="Maximum papers/nodes in graph"),
    db: Session = Depends(get_db)
) -> RelationshipGraphResponse:
    return build_relationship_graph(
        db=db,
        topic=topic,
        start_year=start_year,
        end_year=end_year,
        min_similarity=min_similarity,
        max_nodes=max_nodes
    )


@router.post(
    "/gaps",
    response_model=GapExplorationResponse,
    summary="Candidate Research-Gap Explorer",
    description=(
        "Synthesize grounded candidate research-gap hypotheses from catalog metadata and evidence. "
        "Strictly discloses local corpus boundaries and never claims global novelty from local absence alone."
    )
)
def post_candidate_gaps(
    request: GapExplorationRequest,
    db: Session = Depends(get_db)
) -> GapExplorationResponse:
    return explore_candidate_gaps(
        db=db,
        request=request
    )


@router.post(
    "/assistant",
    response_model=ResearchAssistantResponse,
    summary="Grounded Research Assistant",
    description=(
        "Query the research assistant to answer questions about papers, methods, "
        "datasets, limitations, DRIUT relationships, and research evolution. "
        "All claims are deterministically linked to verified source evidence passages."
    )
)
def post_research_assistant(
    request: ResearchAssistantRequest,
    db: Session = Depends(get_db)
) -> ResearchAssistantResponse:
    return answer_research_question(
        db=db,
        request=request
    )


@router.get(
    "/ai/status",
    response_model=AIProviderStatus,
    summary="AI Subsystem Status & Capabilities",
    description=(
        "Returns the active state of Ollama local models, Groq cloud failover, "
        "and deterministic fallback. Never exposes API keys or credentials."
    ),
)
async def get_ai_status() -> AIProviderStatus:
    coordinator = get_ai_coordinator()
    return await coordinator.get_status()

