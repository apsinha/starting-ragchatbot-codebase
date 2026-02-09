"""Shared fixtures for backend tests."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional


# ---------------------------------------------------------------------------
# Pydantic models mirroring app.py (re-defined here to avoid importing app.py
# which triggers module-level side-effects: RAGSystem init, static-file mount)
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class SourceItem(BaseModel):
    name: str
    link: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_rag_system():
    """A MagicMock standing in for RAGSystem with sane defaults."""
    rag = MagicMock()
    rag.query.return_value = (
        "Test answer",
        [{"name": "Course A", "link": "https://example.com"}],
    )
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    rag.session_manager.create_session.return_value = "session_new"
    return rag


def _build_test_app(rag_system):
    """Build a minimal FastAPI app whose endpoints mirror app.py but use
    an injected rag_system instead of a real one."""

    test_app = FastAPI()

    @test_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(
                answer=answer, sources=sources, session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return test_app


@pytest.fixture
def test_app(mock_rag_system):
    """A FastAPI app wired to the mock_rag_system."""
    return _build_test_app(mock_rag_system)


@pytest.fixture
def client(test_app):
    """A TestClient for the test app."""
    return TestClient(test_app)
