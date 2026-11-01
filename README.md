# MR Assistant

Agentic assistant for medical reps in Indian pharma: call planning, doctor prioritization,
live KPIs, pre-call briefs, post-call voice notes and next best action.
Built on a fully fictional dataset (company "Example Pharma"): synthetic brand codes (AX-R1, CA-R1, …), numbered
hospitals and chemists, non-dialable phone numbers. No real company, product or person data; any resemblance
of doctor or employee names to real people is coincidental.

**Status: foundation-v1 complete (v0.5.1, data-v2).** Data, database, gold views, 33 data tools, a golden
question set and full documentation are in place and frozen. Next: building agents (see `docs/plan.md`).

## Setup

```bash
# 1. Python environment
conda create -n mrchatbot python=3.11 --no-default-packages
conda activate mrchatbot
pip install -r requirements.txt          # installs the mr_assistant package (editable) + dev tools

# 2. Database (Postgres 16 + pgvector in Docker)
cp .env.example .env                     # set POSTGRES_PASSWORD and POSTGRES_APP_PASSWORD
docker compose up -d

# 3. Build the database (~10 s, safe to rerun any time)
python scripts/build_db.py

# 4. Check everything
python -m pytest -q                      # security, tools and golden-set tests
```

`build_db.py` verifies the frozen dataset (data-v2 checksums), recreates schema `core`, loads all 21 tables,
creates the gold views, descriptions and row-level security - in one transaction.

## Using the tools

```python
from mr_assistant.db import as_employee
from mr_assistant import tools

with as_employee(990003) as db:                      # BO Soumya Banerjee, Kolkata
    for d in tools.get_priority_doctors(db, limit=3):
        print(d.doctor_name, d.score, d.reasons)
    print(tools.get_rep_kpis(db, 202609))
```

- Every query runs as a user: row-level security limits a BO to their territory and a manager to their team.
- Tools are read-only and return Pydantic models (easy to turn into JSON for an LLM).
- See `docs/tools.md` for all 33 tools and `docs/data_dictionary.md` for every table, view and column.

Personas for testing: 990001 Karthikeyan R (BO Chennai, star), 990002 Aniket Kulkarni (BO Pune, coverage gap),
990003 Soumya Banerjee (BO Kolkata, declining share), 990004 Priya Deshpande (BO Mumbai, busy but short calls),
990005 Rohit Malhotra (BO Delhi, new after a handover), 991012 Gurpreet Singh (ABM Delhi), 993011 Rajesh Shah (ZBM).

## Database users

| User | Used by | Rights |
|---|---|---|
| `mrchatbot` | `build_db.py` (admin) | Owner of everything |
| `mr_app` | Tools, agents, API | Read-only; row-level security applies; identity set per transaction |

## Golden questions

`evals/golden_questions.jsonl`: 59 realistic questions from reps and managers (KPIs, coverage, doctors,
planning, market, engagement, manager views, security refusals), each with the expected answer, how to check it,
the tools an agent would use, and the SQL that reproduces the answer. `tests/test_golden.py` re-checks them all.
These are the benchmark for every agent you build.

## Project layout

| Path | Contents |
|---|---|
| `src/mr_assistant/` | Package: `config.py`, `db.py` (`as_employee`), `errors.py`, `tools/` (33 data tools) |
| `db/` | `schema.sql` (21 tables), `views.sql` (gold views), `comments.sql` (descriptions), `security.sql` (RLS), `init/` |
| `data/` | Frozen dataset data-v2 (Parquet), `DATA_VERSION.json`, `answer_key/` (hidden ground truth) |
| `evals/` | Golden question set and its builder |
| `scripts/` | `build_db.py`, `gen_docs.py`, banned-terms check, git hook installer |
| `tests/` | pytest: row-level security, tools, golden set |
| `docs/` | `plan.md`, `tools.md`, `data_dictionary.md` |
| `synth/` | Synthetic data generator (reference only) |

## Banned-terms guard (before the first commit)

```bash
cp .banned_terms.example .banned_terms     # list real names that must never be committed
git init && bash scripts/install_hooks.sh  # pre-commit hook scans code, docs and Parquet data
```

## Features

| Version | Feature |
|---|---|
| v0.0.1 | Project setup, banned-terms guard |
| v0.0.2 | Postgres 16 with pgvector and pg_trgm in Docker |
| v0.2.0 | Frozen dataset data-v1, full schema, one-command DB build |
| v0.3.0 | Gold view `doctor_visit_compliance` |
| v0.4.0 | Role `mr_app` and row-level security |
| v0.5.0 | **foundation-v1**: all gold views, `mr_assistant` package, 33 data tools, golden questions, docs |
| v0.5.1 | Public-safety data revision (data-v2): synthetic brand and business-unit names, numbered hospitals and chemists, non-dialable phones |

## Changelog

### v0.5.1 (data-v2)
- All brand names replaced with synthetic codes (own AX-R1…AX-R6, AX-C1…AX-C6; competitors CA-/CB-/CC-…) after two
  invented names turned out to match real products; business units renamed to descriptive names (e.g. Respiratory BU);
  company renamed to Example Pharma.
- Hospitals and chemists numbered (e.g. Hospital H-07, Chemist C-112); registration and drug-licence numbers marked SYN;
  phone numbers start with 0 so they can never reach a real person.
- Structure, row counts, figures and stories unchanged; tests and golden questions updated to the new names.

### v0.5.0 (foundation-v1)
- Gold views: `rep_monthly_kpi`, `rx_monthly`, `market_share`, `doctor_360`, `brand` (all `security_invoker`).
- Package `mr_assistant`: settings (pydantic-settings), connection pool, `as_employee()` read-only transactions
  with RLS identity, savepoint per query so one failed query never breaks a session.
- 33 read-only data tools across identity, doctors, visits/KPIs, planning, market and engagement; all < 200 ms.
- Golden question set (59) with reproducible expected answers; data dictionary and tool catalog generated from
  the database and code; descriptions stored in the database (`db/comments.sql`).
- Tests: 92 (security, tools, golden set), ~10 s.

### v0.4.0
- `db/security.sql`: role `mr_app`, territory / team policies, fail closed; `security_invoker` views; RLS tests.

### v0.3.0
- `db/views.sql`: schema `analytics` with `doctor_visit_compliance`.

### v0.2.0
- Dataset frozen as data-v1; `db/schema.sql` with all 21 tables; `scripts/build_db.py`.

### v0.0.2 / v0.0.1
- Postgres in Docker; conda env, project layout, banned-terms check and pre-commit hook.
