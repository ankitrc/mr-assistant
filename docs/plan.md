# MR Assistant – Project Plan

Build the agentic system first; then add evaluation, observability, JWT auth and the rest on top.
Foundation (data, database, views, tools, golden questions, docs) is complete and frozen as **foundation-v1**.

## Main plan

| Milestone | Who | What we build | Outcome | Release |
|---|---|---|---|---|
| ✅ **0–1. Setup + data foundation** | Done | Conda env, Postgres 16 + pgvector in Docker, frozen dataset (21 tables, now data-v2), full schema with constraints, first gold view, row-level security with tests | A trustworthy, secured database rebuilt in one command | v0.4.0 |
| ✅ **A. Foundation complete** | Done | Gold views (KPIs, Rx, share, Doctor 360), Python package (settings, pool, `as_employee`), 33 tested data tools, 59 golden questions with reproducible answers, data dictionary and tool catalog | Everything agents need exists and is frozen; no more data work | v0.5.0 |
| **B. First agent** | You | LLM connection via LiteLLM, tool calling built from scratch, a ReAct agent, then the same agent in LangGraph, a streaming CLI with a debug trace | An agent that answers KPI and doctor questions from real data | v0.6–0.9 |
| **C. Multi-agent** | You | Supervisor routing to KPI and planner agents, conversation memory in Postgres, long-term preferences, identity-aware tools (BO vs manager) | A team of agents that remembers context and respects who is asking | v0.10–0.13 |
| **D. Pre-call brief** | You | Parallel sub-agents (Doctor 360, last call, products, what changed), grounded 3-minute brief, guarded text-to-SQL agent | Fast, fact-checked briefs; open questions answered safely | v0.14–0.16 |
| **E. Human-in-the-loop** | You | Write paths with migrations, tour plan drafting and approval (BO → ABM), slot booking, message drafts with consent checks, action log | Agents propose, people approve, every action is audited | v0.17–0.20 |
| **F. Intelligence** | You | Note extraction, voice notes (speech-to-text), embeddings and RAG over notes and content, NBA agent, rep coach, scenario planner | The full agentic system from the requirements | v0.21–**v1.0.0** |
| **G. Evaluation + observability** | You | Langfuse tracing and prompt management, DeepEval scoring on the golden set, regression gate, cost and latency tracking | Measurable quality; regressions caught before release | v1.1–1.3 |
| **H. Production** | You | FastAPI (streaming chat, approvals), Keycloak login with JWT, guardrails and PII masking, model serving, containers and CI, web and mobile apps | A deployable product | v1.4–**v2.0.0** |

## What you'll learn

| Area | Technology / concept | What you'll learn | Milestone |
|---|---|---|---|
| Database | PostgreSQL | Schema design, constraints, indexes, views, transactions | ✅ 0–1, A |
| | Row-level security | Per-user data isolation enforced by the database | ✅ 0–1, C |
| | pg_trgm / pgvector | Fuzzy name search; vector similarity search | ✅ A, F |
| | Alembic | Versioned schema migrations | E |
| Containers | Docker, Docker Compose | Running services; later building your own images (dockerization) | ✅ 0–1, H |
| LLM fundamentals | LiteLLM | One API for any model (Azure OpenAI, Ollama, vLLM), fallbacks, cost tracking | B |
| | Prompting, tokens, temperature | How models behave and how to steer them | B |
| | Structured outputs (Pydantic) | Reliable JSON from LLMs for routing, extraction and briefs | B, C, D |
| Agents | Tool calling | How an LLM chooses and calls functions, built by hand first | B |
| | ReAct loop | Reason → act → observe; stop conditions; error handling | B |
| | LangGraph | State, nodes, edges, tool nodes, streaming | B |
| | Multi-agent patterns | Supervisor routing, specialist agents | C |
| | Memory | Conversation checkpoints, summarisation, long-term preferences | C |
| | Parallelism | Fan-out / fan-in sub-agents (Send API) | D |
| | Human-in-the-loop | Interrupts, approvals, resuming later | E |
| Retrieval | Text-to-SQL + sqlglot | Natural language → safe SQL, defence in depth | D |
| | Embeddings (BGE-M3) | Turning text into vectors; multilingual search | F |
| | RAG + hybrid search | Chunking, retrieval, grounding answers in sources | F |
| | Docling | Parsing PDFs and decks into clean, searchable content | F |
| Voice | faster-whisper, FFmpeg | Speech-to-text for voice notes; audio processing | F |
| Background work | Celery + Valkey | Running slow jobs (transcription, embeddings) outside the request | F |
| | MinIO | Object storage for audio and documents (S3-compatible) | F |
| Planning / ML | OR-Tools | Optimising monthly tour plans under constraints | E |
| | Rules + LightGBM | Rule-based NBA first, learned scoring later | F |
| | StatsForecast | Forecasts for what-if scenarios | F |
| Quality | pytest | Testing tools, security and agents | ✅ A onwards |
| | DeepEval / Ragas | Scoring routing, tool use, correctness, faithfulness | G |
| Observability | Langfuse | Tracing conversations, prompt versions, cost | G |
| | OpenTelemetry, Prometheus, Grafana | Service metrics, dashboards, alerts | G, H |
| API | FastAPI + SSE | Building APIs, streaming agent responses, approval endpoints | H |
| Security | Keycloak, OIDC, JWT | Login, roles, passing identity to the database | H |
| | NeMo Guardrails, Presidio | Blocking unsafe or off-label output; masking personal data | H |
| Serving | Ollama, vLLM, Qwen3 | Running open models locally and on GPU servers | B, H |
| Delivery | CI pipeline, Trivy | Automated tests, image scanning, one-command deploys | H |
| Frontend | React, React Native | Web app for reps and managers; mobile app with voice notes | H |

## Rules

1. Foundation-v1 is frozen: data, schema, views and tools are used, not changed. Write paths (Milestone E) add migrations without touching existing data.
2. Install only the packages a task needs (add them to `pyproject.toml`).
3. A task is done only when its "done when" check passes; keep `python -m pytest` green.
4. After every release: update the README (Features, Changelog) and this plan, commit and tag.
5. Nothing company-specific is ever committed (`.banned_terms` + pre-commit hook).
