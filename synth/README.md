# Synthetic data generator – MR Assistant (India)

Generates a realistic, fully fictional pharma field-force dataset for a fictional company,
**Example Pharma**, with two business units: Respiratory BU and Cardio-Metabolic BU (diabetes, cardio, metabolic).
Brand names are synthetic codes (own brands AX-R1…AX-R6, AX-C1…AX-C6; competitors CA-/CB-/CC-…) so they can never
match a real product. Hospitals and chemists are numbered, registration and licence numbers carry "SYN", and
phone numbers start with 0 (not dialable).
All companies, brands, product codes, people, emails, mobiles and social profiles are invented.

21 tables as Parquet in `data/parquet/` (shape = rows, columns incl. 4 audit columns):

| Phase | Table | Shape |
|---|---|---|
| 1 | calendar_day | (1095, 18) |
| 1 | geography | (40, 20) |
| 1 | employee | (23, 20) |
| 1 | doctor | (864, 39) |
| 1 | mcl | (950, 17) |
| 1 | dcr_call | (30726, 21) |
| 2 | business_unit | (6, 12) |
| 2 | kpi_target | (72, 10) |
| 2 | tour_plan | (31198, 25) |
| 2 | clinic | (1117, 19) |
| 2 | agent_action_log | (4262, 18) |
| 3 | product | (42, 21) |
| 3 | chemist | (240, 17) |
| 3 | rcpa_entry | (84068, 15) |
| 3 | doctor_brand_plan | (53234, 17) |
| 3 | dcr_call_product | (75907, 14) |
| 4 | call_note | (10300, 30) |
| 4 | communication | (10595, 25) |
| 4 | content | (83, 18) |
| 4 | formulary_listing | (580, 11) |
| 4 | nba_recommendation | (1155, 17) |

`data/answer_key/` holds hidden ground truth (rep profiles, doctor traits) for evaluation. Never load it for agents.

Key dates: history 1 Nov 2024 – 27 Oct 2026 (as-of); app pilot from 1 Sep 2026 (voice notes, agent drafts,
NBA, action log); November 2026 tour plans in draft / submitted / approved states.

Built-in stories (one per rep): star performer, coverage gap, declining share to a competitor,
busy but ineffective, and a new rep after a territory handover.

Notes:
- Competitor brands and companies are fictional. Content key messages and claims are placeholders.
- `embedding` columns are empty; fill them with an embedding model when loading.
- Festival holiday dates for 2026-27 are approximate.

The dataset is frozen as **data-v2** (`data/DATA_VERSION.json` at the repo root holds the checksums).
This generator is kept for reference; regenerating is not part of the normal workflow.

Regenerate and validate (deterministic; 55 integrity checks; writes to `synth/data/`):

    pip install -r requirements.txt
    python run.py            # all phases
    python run.py 1 2        # selected phases

Settings (as-of date, seeds, company name) are in `generator/config.py`.
