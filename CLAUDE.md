# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A RAG (Retrieval-Augmented Generation) chatbot that answers questions about course materials. FastAPI backend serves both the API and a static frontend. Uses ChromaDB for vector storage and Anthropic Claude for AI generation with tool-use.

## Commands

### Run the app
```bash
cd starting-ragchatbot-codebase && ./run.sh
# or manually:
cd starting-ragchatbot-codebase/backend && uv run uvicorn app:app --reload --port 8000
```
App serves at http://localhost:8000, API docs at http://localhost:8000/docs.

### Install dependencies
```bash
cd starting-ragchatbot-codebase && uv sync
```

### Environment setup
Create `.env` in the project root with `ANTHROPIC_API_KEY=<key>`.

## Architecture

### Query Flow (the critical path)

`script.js sendMessage()` → `POST /api/query` → `app.py query_documents()` → `RAGSystem.query()` → `AIGenerator.generate_response()` → **Anthropic API call #1** (with `search_course_content` tool attached)

Claude then either returns a direct answer OR invokes the tool, which triggers:
`CourseSearchTool.execute()` → `VectorStore.search()` → ChromaDB query → formatted results → **Anthropic API call #2** (with search results, no tools) → final answer

This two-call pattern (tool-augmented then synthesis) is the core of the RAG system.

### Backend Components (`backend/`)

- **`app.py`** — FastAPI entry point. Two API routes (`POST /api/query`, `GET /api/courses`). Mounts `../frontend` as static files at `/`. On startup, auto-loads all docs from `../docs/`.
- **`rag_system.py`** — Orchestrator. Owns all components and wires them together. The `query()` method is the main pipeline.
- **`ai_generator.py`** — Anthropic SDK wrapper. Handles the two-step tool-use flow: initial call with tools → execute tool → follow-up call without tools. System prompt is a class constant (`SYSTEM_PROMPT`).
- **`vector_store.py`** — ChromaDB wrapper with **two collections**: `course_catalog` (course-level metadata, used for fuzzy name resolution) and `course_content` (chunked text, used for semantic search). The `search()` method first resolves a course name via vector similarity on the catalog, then queries content.
- **`document_processor.py`** — Parses structured `.txt` files (expected format: Course Title/Link/Instructor header, then `Lesson N:` markers). Chunks text into ~800-char segments with 100-char sentence-boundary overlap.
- **`search_tools.py`** — Tool abstraction layer. `Tool` ABC → `CourseSearchTool` implementation. `ToolManager` registry provides tool definitions to the Anthropic API and dispatches execution.
- **`session_manager.py`** — In-memory conversation history. Stores last 2 exchanges per session. Not persisted across restarts.
- **`config.py`** — Dataclass with all tunables (chunk size, overlap, max results, model name, ChromaDB path).
- **`models.py`** — Pydantic models: `Course`, `Lesson`, `CourseChunk`.

### Frontend (`frontend/`)

Vanilla HTML/CSS/JS. Uses `marked.js` for markdown rendering. Communicates via `/api/query` and `/api/courses`. Manages `session_id` client-side (null on first message, reused after).

### Key Conventions

- Always use `uv` to run Python and manage dependencies. Do not use `pip` directly.

- Course documents go in `docs/` as `.txt` files with a specific header format (see `document_processor.py` lines 97-103).
- The backend runs from the `backend/` directory — relative paths like `../docs` and `../frontend` are resolved from there.
- ChromaDB data persists at `backend/chroma_db/`. Existing courses are skipped on startup (dedup by title).
- No test suite exists currently.
