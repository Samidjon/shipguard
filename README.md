# 🚢 ShipGuard

### AI-Assisted Shipping Document Verification System

ShipGuard helps shipping operations teams triage incoming email and validate
Shipping Instructions (SI) against draft Bills of Lading (BL).

A deterministic engine produces every verdict. Google Gemini is used only to
classify email intent and to explain results in plain language.

---

## 🎯 Problem

Shipping operations handle large volumes of email and attachments. Details such
as shipper, consignee, notify party, ports, container count and gross weight can
differ between a Shipping Instruction and a Bill of Lading, and checking them by
hand is slow and easy to get wrong.

ShipGuard automates the triage: it identifies the relevant emails, extracts the
document fields, compares them, and explains what differs.

---

## 💡 Solution

```text
Incoming shipping email
        ↓
Email classification            (rule-based)
        ↓
SI / BL document detection
        ↓
Document reading (txt, pdf, docx, xlsx)
        ↓
Field extraction
        ↓
Deterministic field comparison  ← the verdict is decided here
        ↓
Gemini explanation layer        (optional, never changes the verdict)
        ↓
Human-readable result
```

**Architecture principle:** Gemini does not decide whether documents match. If
the AI layer is unavailable, the verification result is still produced.

---

## ✨ Features

### Email classification

Five categories: `BL_COMPARISON`, `SI_REQUEST`, `INVOICE_QUERY`, `GENERAL`,
`SPAM`.

### Document reading

Plain text, PDF, DOCX (including tables) and XLSX attachments are flattened to
text. A PDF with no extractable text is reported rather than silently skipped.

### Seven-field comparison

| Field | Description |
|-------|-------------|
| `shipper` | Shipping party |
| `consignee` | Consignee |
| `notify_party` | Notify party |
| `port_of_loading` | Port where cargo is loaded |
| `port_of_discharge` | Destination discharge port |
| `container_count` | Number of containers |
| `gross_weight_kg` | Gross cargo weight |

SI and BL frequently label the same field differently (`Port of Loading` vs
`Load Port` vs `POL`). Fields are aligned by meaning, not by header text.
Comparison also ignores cosmetic differences such as case, spacing and a
trailing UN/LOCODE (`NHAVA SHEVA, INDIA (INNSA)` matches `NHAVA SHEVA, INDIA`).

### Verification statuses

- **OK** — all required values are present and match.
- **MISMATCH** — one or more fields differ; the differing fields are listed.
- **NEEDS_REVIEW** — the comparison cannot be completed safely, with a reason:
  `missing_attachment`, `wrong_doc_type`, `unreadable`, or `missing_value`.

ShipGuard reports `NEEDS_REVIEW` instead of guessing. A Shipping Instruction
with no gross weight is escalated for human review rather than assuming the
Bill of Lading is correct.

### AI layer

Gemini performs two jobs:

1. **Email understanding** — category, short summary, confidence score.
2. **Result explanation** — a human-readable account of the differences the
   deterministic engine found, plus a recommended next step.

Both degrade gracefully: on API failure the dashboard still shows the
deterministic verdict.

---

## 🖥️ Dashboard

The Streamlit dashboard shows email selection, email content, attached
documents, the verification result, the AI analysis and explanation, a
field-by-field comparison table, review details and the raw technical result.

---

## 🛠️ Technology

- **UI** — Streamlit
- **Processing** — Python, pypdf, python-docx, openpyxl, PyMuPDF, pandas
- **AI** — Google Gemini via `google-genai`
- **Testing** — pytest

---

## 📁 Project structure

```text
shipguard/
├── app.py                  # Streamlit entry point (thin shim)
├── run_pipeline.py          # CLI entry point for the whole inbox
├── pyproject.toml           # pytest configuration
├── requirements.txt
├── .env.example
├── results.json             # generated: full output incl. diagnostics
├── submission.json          # generated: official hackathon shape
│
├── shipguard/               # the package
│   ├── config.py            # paths, compared fields, model selection
│   ├── loader.py            # inbox access (vendored from the bundle)
│   ├── classifier.py        # email categories
│   ├── document_reader.py   # txt / pdf / docx / xlsx → text
│   ├── extractor.py         # text → the seven fields
│   ├── comparator.py        # normalization + comparison
│   ├── pipeline.py          # orchestration and verdicts
│   ├── ai_service.py        # Gemini layer
│   └── ui/app.py            # Streamlit dashboard
│
├── scripts/                 # diagnostics (see below)
├── tests/                   # pytest suite
└── sdoc-hackathon-bundle/   # organizer-provided dataset
    ├── inbox/
    └── attachments/
```

---

## 🚀 Local setup

### 1. Clone

```bash
git clone https://github.com/Samidjon/shipguard.git
cd shipguard
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

No install step is needed for the `shipguard` package itself — it is imported
straight from the repository root.

### 4. Configure Gemini (optional)

The pipeline runs without an API key; only the AI explanation layer needs one.
Create a `.env` file:

```text
GEMINI_API_KEY=your_gemini_api_key_here
```

Never commit a real key.

### 5. Run

```bash
python run_pipeline.py     # process the inbox, write results + submission
streamlit run app.py       # open the dashboard
pytest                     # run the test suite
```

---

## ⚙️ Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | For AI features only | Gemini credentials. Read from the environment or Streamlit secrets. |
| `GEMINI_MODEL` | No | Pin one Gemini model. Unset, ShipGuard tries the candidates in `shipguard/config.py` and skips any that the API reports as unavailable. |
| `SHIPGUARD_DATA` | No | Point at a different dataset folder or an HTTP inbox URL. Defaults to `sdoc-hackathon-bundle/` in the repo root. |
| `SHIPGUARD_GROUND_TRUTH` | Scoring only | Path to the organizers' `ground_truth.json`. That package holds the answer key and lives outside this repository — never commit it. |
| `SHIPGUARD_SCORER` | No | Folder containing the organizers' `scoring.py`. Derived from the ground-truth path by default. |

Available Gemini models depend on your key. List the ones you can use with:

```python
from shipguard.ai_service import discover_models
print(discover_models())
```

---

## 🔬 Diagnostics

```bash
python scripts/diagnose_pipeline.py            # stage-by-stage funnel + field counts
python scripts/inspect_mismatches.py           # SI vs BL values for flagged defects
python scripts/inspect_missing.py email_004    # extracted data + raw text per email
python scripts/inspect_wrong_docs.py           # BL attachments that are another document
python scripts/inspect_categories.py SPAM      # browse emails by category
python scripts/score_submission.py             # official score (needs SHIPGUARD_GROUND_TRUTH)
```

---

## 🧪 Tests

```bash
pytest
```

191 tests covering label aliasing, placeholder handling (`N/A`, `TBA`, `____MT`
become "missing", never a value), LOCODE-insensitive port comparison, the
word-boundary phrase matcher, every classification rule and its precedence,
and every verdict path including all four `NEEDS_REVIEW` reasons. Tests that
call the live Gemini API are skipped automatically when `GEMINI_API_KEY` is not
set.

---

## 📊 Dataset and output

The provided dataset contains **520 emails**. A full run produces:

- `results.json` — every email plus diagnostic detail for review cases.
- `submission.json` — one entry per email with `category`, `status`,
  `review_reason`, `has_defect` and `defect_fields`, matching the shape of
  `sdoc-hackathon-bundle/sample_submission.json`.

Both files are written to the repository root regardless of the working
directory the pipeline is launched from.

Current run over the full dataset:

| Status | Count |
|--------|-------|
| OK | 457 |
| MISMATCH | 46 |
| NEEDS_REVIEW | 17 |

| Category | Count |
|----------|-------|
| BL_COMPARISON | 220 |
| SI_REQUEST | 125 |
| INVOICE_QUERY | 75 |
| GENERAL | 60 |
| SPAM | 40 |

---

## 📈 Measured accuracy

Scored with the organizers' own scorer against their reference answers:

| Axis | Weight | Result |
|------|--------|--------|
| End-to-end defect catch | 50% | **46/46 = 1.000** |
| Stage-3 defect F1 | 20% | **1.000** (recall 1.000, precision 1.000, field-F1 1.000, exact-match 1.000) |
| Stage-1 classification macro-F1 | 30% | **1.000** (accuracy 1.000, all five categories 1.00 / 1.00 / 1.00) |
| **Final score** | | **1.0000** |

Reliability is reported as a separate axis: escalation precision 1.000,
recall 0.850, F1 0.919 — 17 escalations against 20 genuinely undecidable
cases.

### Running the scorer

The organizer package contains the answer key, so it is **not** part of this
repository. Point ShipGuard at your local copy:

```powershell
$env:SHIPGUARD_GROUND_TRUTH = "D:\path\to\sdoc-hackathon-docker\data_v2\ground_truth.json"
python scripts/score_submission.py
```

The harness calls the organizers' `scoring.score_all`, so the numbers are
theirs rather than a local reimplementation. It prints the per-category
breakdown and a confusion matrix, and fails if Stage-3 defect F1 or the
end-to-end rate ever drops below 1.000.

Caveat worth stating plainly: the classification rules were refined using this
scoreboard as feedback, which the organizers' brief explicitly invites. A
perfect Stage-1 score on the same data that guided the rules is therefore not
an unbiased estimate of accuracy on unseen email.

---

## ☁️ Deployment

Deployed on Streamlit Community Cloud with `app.py` as the main file:

https://shipguard-kjxefg6xu7p8t4iedbwyi3.streamlit.app/

Source: https://github.com/Samidjon/shipguard

---

## 🔐 Security

Credentials never live in source. Local development uses a `.env` file, cloud
deployment uses Streamlit Secrets, and the repository contains only
`.env.example` with placeholder values.

---

## 🏆 Hackathon

Built for the Averis x Monash Hackathon 2026.

Core idea: automate repetitive shipping document verification while keeping the
final decision deterministic, transparent and explainable.
