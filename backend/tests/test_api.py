"""Tests for FastAPI API endpoints (/api/query, /api/courses, /)."""

import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:

    def test_query_with_session_id(self, client, mock_rag_system):
        """Existing session_id is forwarded to RAGSystem.query."""
        resp = client.post(
            "/api/query",
            json={"query": "What is AI?", "session_id": "session_42"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "Test answer"
        assert data["session_id"] == "session_42"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["name"] == "Course A"

        mock_rag_system.query.assert_called_once_with("What is AI?", "session_42")
        mock_rag_system.session_manager.create_session.assert_not_called()

    def test_query_without_session_id(self, client, mock_rag_system):
        """No session_id -> a new session is created."""
        resp = client.post("/api/query", json={"query": "Hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "session_new"
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_query_with_null_session_id(self, client, mock_rag_system):
        """Explicit null session_id is treated the same as omitted."""
        resp = client.post(
            "/api/query", json={"query": "test", "session_id": None}
        )
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "session_new"

    def test_query_missing_body(self, client):
        """Missing JSON body -> 422 validation error."""
        resp = client.post("/api/query")
        assert resp.status_code == 422

    def test_query_missing_query_field(self, client):
        """JSON body without required 'query' field -> 422."""
        resp = client.post("/api/query", json={"session_id": "s1"})
        assert resp.status_code == 422

    def test_query_server_error(self, client, mock_rag_system):
        """RAGSystem raises -> endpoint returns 500 with detail."""
        mock_rag_system.query.side_effect = RuntimeError("DB down")
        resp = client.post("/api/query", json={"query": "fail"})
        assert resp.status_code == 500
        assert "DB down" in resp.json()["detail"]

    def test_query_sources_with_no_link(self, client, mock_rag_system):
        """Sources may omit the link field."""
        mock_rag_system.query.return_value = (
            "Answer",
            [{"name": "Course X"}],
        )
        resp = client.post("/api/query", json={"query": "x"})
        assert resp.status_code == 200
        assert resp.json()["sources"][0]["link"] is None

    def test_query_empty_sources(self, client, mock_rag_system):
        """No sources returned -> empty list in response."""
        mock_rag_system.query.return_value = ("Direct answer", [])
        resp = client.post("/api/query", json={"query": "general"})
        assert resp.status_code == 200
        assert resp.json()["sources"] == []


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:

    def test_get_courses(self, client):
        """Returns course stats from the RAG system."""
        resp = client.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_courses"] == 2
        assert data["course_titles"] == ["Course A", "Course B"]

    def test_get_courses_empty(self, client, mock_rag_system):
        """No courses loaded -> zeros."""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        resp = client.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_courses_server_error(self, client, mock_rag_system):
        """Analytics failure -> 500."""
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("oops")
        resp = client.get("/api/courses")
        assert resp.status_code == 500
        assert "oops" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET / (static files / root)
# ---------------------------------------------------------------------------

class TestRootPath:

    def test_root_returns_404_without_static_files(self, client):
        """Test app has no static mount -> root returns 404."""
        resp = client.get("/")
        assert resp.status_code == 404
