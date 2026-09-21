---
name: shipguard-pipeline
description: Work on the ShipGuard shipping-document verification pipeline — classify emails, extract SI/BL fields, compare the 7 required fields, and produce submission.json. Use when editing anything under shipguard/ (config.py, classifier.py, extractor.py, comparator.py, pipeline.py, document_reader.py, ai_service.py, ui/app.py), when running run_pipeline.py or the tests, when using the scripts/ diagnostics, when scoring a submission, when debugging OK/MISMATCH/NEEDS_REVIEW verdicts, or when generating the hackathon submission.
metadata:
  project: ShipGuard
  hackathon: Averis x Monash Hackathon 2026 (SDOC)
---

# ShipGuard pipeline skill

ShipGuard reads a shipping inbox and, per email, (1) classifies it and (2) for
`BL_COMPARISON` emails compares a Shipping Instruction (SI) against a draft Bill
of Lading (BL) across 7 fields, emitting `OK` / `MISMATCH` / `NEEDS_REVIEW`.

## Core architecture principle (do not violate)

The **deterministic engine decides the verdict**. Gemini AI only *classifies
intent* and *explains* results in natural language. Never let AI change the
`status`, `has_defect`, or `defect_fields`. Any change that makes an LLM the
source of truth for a verdict is wrong.

## Layout

```
app.py                   thin Streamlit shim -> shipguard.ui.app (runpy)
run_pipeline.py           CLI entry -> shipguard.pipeline:main
shipguard/
  config.py               paths, FIELDS, Gemini model selection
  loader.py               inbox access (vendored from the organizer bundle)
  classifier.py           email categories
  document_reader.py      txt / pdf / docx / xlsx -> text
  extractor.py            text -> the 7 fields (3 passes)
  comparator.py           normalization + comparison
  pipeline.py             orchestration, verdicts, submission writing
  ai_service.py           Gemini layer
  ui/app.py               Streamlit dashboard
scripts/                  diagnostics
tests/                    pytest suite
sdoc-hackathon-bundle/    organizer dataset (do not modify)
```

`shipguard/config.py` is the single source of truth for the compared fields,
the dataset path, the output paths and the Gemini model. Do not reintroduce
local copies of any of those.

## The 7 compared fields (exact keys, in this order)

```
shipper, consignee, notify_party, port_of_loading,
port_of_discharge, container_count, gross_weight_kg
```

Defined once in `config.FIELDS`. Import it; never inline the list.

## Data flow

```
Inbox(email) -> classify_email()               (classifier.py)
   └─ if BL_COMPARISON:
        find_attachment(..., "SI"/"BL")         (pipeline.py)
        read_document()                         (document_reader.py)
        detect_wrong_doc_type()                 (pipeline.py, checks BL text)
        extract_document(text, "SI"/"BL")       (extractor.py)
        get_missing_fields()                    (pipeline.py)
        compare_documents(si, bl)               (comparator.py, normalized)
      -> OK | MISMATCH(+defect_fields) | NEEDS_REVIEW(+review_reason)
```

## Classification rules (classifier.py)

**The subject is deliberately unreliable — the intent lives in the body.** A
routing-code subject (`AFEMY - MOMBASA_KENYA - ...`) or a thread subject
(`TO CONFIRM DOCS`) says little; the body states what is actually being asked.
Rules match subject + body and the ORDER carries the logic:

1. attached SI + BL pair -> `BL_COMPARISON` (strongest evidence, nothing preempts it)
2. SI transmittal (subject `^SI[-_:]`, or body "find shipping instruction for")
   -> `SI_REQUEST`. Must precede comparison: these messages name the BL in
   passing ("HOUSE BL", "SURR BL") and would otherwise be read as checks.
3. comparison intent -> `BL_COMPARISON` ("draft bl", "bl draft", "draft bill of
   lading", "amend bl", "for checking", "check the details", "bl matches the si",
   plus the confirm/verify/compare-docs family)
4. spam
5. operational reports -> `GENERAL` ("berthing report", "update summary",
   "outstanding bl", "loading completed", "all pending shipments"). Placed
   before the weak SI/billing keywords so a misleading subject cannot hijack a
   berthing report.
6. explicit SI requests ("request si", "si needed", "cust si", ...)
7. automated bot notices -> `GENERAL` ("automated notification", "no action
   required", "rpa bot")
8. billing intent -> `INVOICE_QUERY` (specific phrases plus an invoice carrying
   a reference number; a bare mention of "invoice" is NOT enough)
9. fallback -> `GENERAL`

Phrase matching uses `_compile()`, whose boundaries are "not adjacent to a
letter or digit" rather than `\b`. **This matters: these subjects separate words
with underscores (`SI NEEDED_ 5RMY-69379`), and `\b`/`\w` treat `_` as a word
character, so a naive word-boundary pattern silently fails on exactly this
traffic.** Internal separators accept whitespace or underscores.

Two phrases are deliberately ABSENT and must not be re-added: `submit si` (only
ever appears in the standing "Submit SI & AED for all pending shipments"
reminder) and `billing process` (only in the RPA subject "Billing Process
Completed"). Both produced nothing but false positives.

## Status rules (authoritative — match pipeline.process_email)

- Not `BL_COMPARISON` -> `OK`, `has_defect=False`.
- `BL_COMPARISON` with NO attachments at all -> `OK`. Nothing was sent, so there
  is nothing to compare and nothing has gone wrong; these are thread replies and
  "please send the draft BL for checking" requests. Escalating them buried the
  reviewer in false alarms (escalation precision was 0.345).
- Attachments present but the SI/BL pair is incomplete -> `NEEDS_REVIEW`,
  `review_reason="missing_attachment"`.
- Read error -> `NEEDS_REVIEW`, `review_reason="unreadable"`.
- BL text is actually invoice / packing list / cert of origin -> `NEEDS_REVIEW`, `review_reason="wrong_doc_type"`.
- Any required field is None on either doc -> `NEEDS_REVIEW`, `review_reason="missing_value"` (do NOT guess).
- All present fields equal -> `OK`.
- >=1 present field differs -> `MISMATCH`, populate `defect_fields`.

`review_reason` values: `wrong_doc_type | missing_attachment | unreadable | missing_value`.

## Extraction & comparison conventions

- **Align fields by meaning, not header text.** SI and BL label the same field
  differently (`Port of Loading` vs `Load Port` vs `POL`). New label variants go
  into `extractor.canonical_field()`.
- Placeholders (`N/A`, `TBA`, `TBC`, `nil`, `____MT`, `___ KG`, dashes) must
  become `None` via `clean_value()` — never treated as a real value.
- Ports: strip trailing UN/LOCODE in parens, e.g. `NHAVA SHEVA, INDIA (INNSA)` ->
  `nhava sheva, india` (`comparator.normalize_port`).
- In `compare_documents`, if either side is `None` the field is **skipped**, not
  a mismatch. Missing values are handled upstream as `missing_value`.
- `container_count` -> int, `gross_weight_kg` -> float (strip commas).

## Commands

Run from the repository root. The `shipguard` package imports without any
install step; no `-e .` is needed and none should be added (it would change the
Streamlit Cloud deployment).

```powershell
python run_pipeline.py      # writes results.json + submission.json to the repo root
pytest                      # full suite
streamlit run app.py        # dashboard (the user runs this, not the agent)
```

Outputs are anchored to the repo root via `config.RESULTS_PATH` /
`config.SUBMISSION_PATH`, so the working directory does not matter.

- `results.json` = full output incl. diagnostics (`missing`, raw `si`/`bl`).
- `submission.json` = official shape: every email_id -> {category, status,
  review_reason, has_defect, defect_fields}. Must cover ALL emails and match
  `sdoc-hackathon-bundle/sample_submission.json` keys.

## Environment variables

- `GEMINI_API_KEY` — required only for the AI layer; from env or Streamlit
  secrets, never hardcoded. The pipeline itself runs without it.
- `GEMINI_MODEL` — optional. Pins one model and disables fallback. Unset,
  `ai_service` walks `config.MODEL_CANDIDATES` and skips any the API reports as
  not found. Use `ai_service.discover_models()` to list what a key allows.
- `SHIPGUARD_DATA` — optional. Alternative dataset folder or HTTP inbox URL.

## Tests

`tests/` is the safety net for every verdict rule — run it before and after
touching extraction, normalization or classification.

- `test_extractor.py` — label aliasing, placeholder handling, numeric parsing,
  all three extraction passes.
- `test_comparator.py` — LOCODE stripping, case/space insensitivity, and that a
  `None` on either side is skipped rather than flagged.
- `test_classifier.py` — the `_compile` boundary matcher (including the
  underscore case), every classification rule, the precedence order, and a
  dataset-wide sanity check (all 5 categories present, none above 90%).
- `test_pipeline.py` — every status rule via in-memory fakes. The
  `run_comparison` fixture monkeypatches `pipeline.read_document`; pass an
  Exception instance as document content to simulate an unreadable file. The
  `si_text` / `bl_text` fixtures (in the root `conftest.py`) build documents
  with deliberately different labels; pass `field=None` to omit a field.
- `test_document_reader.py` — real bundle attachments, incl. xlsx.
- `test_ai_service.py` — model override/fallback and graceful degradation. Live
  API tests are `skipif` without `GEMINI_API_KEY`.

Expected: 191 passed, 3 skipped without a Gemini key.

## Diagnostics

```powershell
python scripts/diagnose_pipeline.py          # stage-by-stage funnel + field counts
python scripts/inspect_mismatches.py         # SI vs BL values for flagged defects
python scripts/inspect_missing.py email_004  # extracted data + raw text per email
python scripts/inspect_wrong_docs.py         # BL attachments that are another doc type
python scripts/inspect_categories.py SPAM    # browse emails by category
python scripts/score_submission.py           # official score + regression gate
```

Scripts add the repo root to `sys.path` themselves, so they work when invoked as
`python scripts/<name>.py`.

## Scoring

The organizer package holds the answer key and lives OUTSIDE the repository
(`.gitignore` blocks `sdoc-hackathon-docker/` and `ground_truth.json` as a
second layer). Never commit it.

```powershell
$env:SHIPGUARD_GROUND_TRUTH = "D:\Coding\sdoc-hackathon-docker\data_v2\ground_truth.json"
python scripts/score_submission.py
```

The harness calls the organizers' `scoring.score_all` — never reimplement the
metric. It prints per-category P/R/F1 plus a confusion matrix and **exits
non-zero if Stage-3 defect F1 or the end-to-end rate falls below 1.000**.

Weighted score = 0.30 x Stage-1 macro-F1 + 0.20 x Stage-3 defect-F1 + 0.50 x
end-to-end rate. Reliability (escalation precision/recall) is reported
separately and is NOT part of the weighted score.

Iterating against this scoreboard is sanctioned by the organizers' brief ("use
the result to improve accuracy"). Reading per-email labels to tune rules is not
— keep rules principled and justified by domain meaning.

## Expected numbers on the provided dataset

520 emails. Derive the count at runtime from `len(Inbox(...).emails())` rather
than hardcoding it; the values below are the current measured result and the
regression signal.

**Score: 1.0000** — Stage-1 macro-F1 1.000 (all five categories 1.00/1.00/1.00),
Stage-3 defect-F1 1.000, end-to-end 46/46. Reliability: escalation precision
1.000, recall 0.850, F1 0.919 (17 flagged vs 20 gold).

| Status | Count |   | Category | Count |
|--------|-------|---|----------|-------|
| OK | 457 |  | BL_COMPARISON | 220 |
| MISMATCH | 46 |  | SI_REQUEST | 125 |
| NEEDS_REVIEW | 17 |  | INVOICE_QUERY | 75 |
|  |  |  | GENERAL | 60 |
|  |  |  | SPAM | 40 |

**Regression gate:** Stage-3 defect-F1 and end-to-end must stay at 1.000. All 46
defect emails sit inside `BL_COMPARISON`, which carries the 50% weight, so only
ever BROADEN comparison detection — never narrow it. Confirm the run log shows
completion ("Total emails: 520", "Processed: 520"); a clean `git status` alone is
a false pass if the pipeline crashed on import.

Honest caveat for any write-up: a perfect Stage-1 score on the same data that
guided the rules is not an unbiased estimate for unseen email.

## Current caveats

- The Gemini model ids in `config.MODEL_CANDIDATES` have **not** been verified
  against the live API (no key was available when they were chosen). The
  fallback chain covers a wrong first entry, but confirm with
  `discover_models()` when a key is at hand.
- Root `app.py` uses `runpy.run_module` rather than an import, because Streamlit
  re-executes its main script on each interaction. Consequence: the UI module is
  not registered in `sys.modules`, so Streamlit's hot-reload watcher may not
  notice edits to `shipguard/ui/app.py` — restart the server after changing it.
- The dashboard has not been verified inside a running Streamlit server, only by
  module execution. Bare-mode runs fail at the `st.session_state` guard, which
  is a bare-mode artifact, not a bug.
- `scripts/inspect_wrong_docs.py` also reports phrases the pipeline does *not*
  treat as wrong document types (`not a shipping instruction`,
  `not an si or bl`). On the current dataset there are zero such cases, so
  widening `detect_wrong_doc_type` would change nothing today.
- `shipguard/loader.py` is vendored from the organizer bundle. Keep it in sync
  with `sdoc-hackathon-bundle/loader.py` instead of editing it locally.

## Environment notes (Windows)

`python` on this machine is the Microsoft Store stub. Use the project venv
(`.\.venv\Scripts\python.exe`) or the `py` launcher. pypdf prints benign
warnings ("incorrect startxref pointer", "EOF marker not found") on some
organizer PDFs — expected noise, not a failure.
