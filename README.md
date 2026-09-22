# 🚢 ShipGuard

### AI-Assisted Shipping Document Verification System

ShipGuard helps shipping operations teams triage incoming email and validate
Shipping Instructions (SI) against draft Bills of Lading (BL).

A deterministic engine produces every verdict. Google Gemini is used only to
classify email intent and to explain results in plain language.

**Measured result: 1.0000** on the organizers' own scorer — 46 of 46 planted
defects caught end to end, classification macro-F1 1.000, zero false alarms
across 200 comparable documents. See [Measured accuracy](#-measured-accuracy)
for the full breakdown and the caveat that comes with it.

### Documentation map

| Section | |
|---------|---|
| [Technical Architecture](#️-technical-architecture) | Pipeline, layers, and the one decision that shaped the design |
| [Implementation Details](#-implementation-details) | Classification rule order, extraction passes, comparison rules, verdict table |
| [Challenges Faced](#-challenges-faced) | Six real problems, how they were found and resolved |
| [Future Roadmap](#️-future-roadmap) | Near term, medium term, production readiness |
| [Measured accuracy](#-measured-accuracy) | Official score, per-axis breakdown, honest caveat |

---

## 🎯 Problem

Shipping operations handle large volumes of email and attachments. Details such
as shipper, consignee, notify party, ports, container count and gross weight can
differ between a Shipping Instruction and a Bill of Lading, and checking them by
hand is slow and easy to get wrong.

ShipGuard automates the triage: it identifies the relevant emails, extracts the
document fields, compares them, and explains what differs.

---

## 🏗️ Technical Architecture

### Pipeline

```text
Incoming shipping email
        ↓
Email classification            (rule-based, body-driven)
        ↓
SI / BL document detection
        ↓
Document reading (txt, pdf, docx, xlsx)
        ↓
Field extraction                (three passes)
        ↓
Normalization + comparison      ← THE VERDICT IS DECIDED HERE
        ↓
Gemini explanation layer        (optional, never changes the verdict)
        ↓
Result for a human operator
```

### The one architectural decision that matters

**Gemini does not decide whether documents match.** A deterministic engine
produces every verdict; the AI layer classifies email intent as a cross-check
and explains the result in plain language. If Gemini is unavailable, the
verification still completes — only the explanation degrades.

The reason is domain-specific: a wrong discharge port means a container on the
wrong continent. A decision entering that process has to be reproducible and
explainable line by line. Two runs of this pipeline produce byte-identical
output, and every compared value traces back to a specific line in the source
document.

### Layers

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Data access | `shipguard/loader.py` | Reads the inbox from a folder or an HTTP endpoint (vendored from the organizer bundle) |
| Classification | `shipguard/classifier.py` | Assigns one of five categories from subject + body |
| Document reading | `shipguard/document_reader.py` | Flattens txt / PDF / DOCX / XLSX to text |
| Extraction | `shipguard/extractor.py` | Pulls the seven fields out of free-form text |
| Comparison | `shipguard/comparator.py` | Normalizes and compares; decides match vs mismatch |
| Orchestration | `shipguard/pipeline.py` | Runs the stages, assigns the verdict, writes the submission |
| Configuration | `shipguard/config.py` | Single source for paths, compared fields and model selection |
| AI | `shipguard/ai_service.py` | Gemini intent classification and explanation, with fallback |
| Interface | `shipguard/ui/app.py` | Streamlit dashboard |

`config.py` is deliberately the only place that defines the seven compared
fields, the dataset location and the model list. Nothing else hardcodes them.

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

## 🔧 Implementation Details

### Classification: the subject lies, the body tells the truth

In this traffic the subject line is actively misleading. An email titled
`TO CONFIRM DOCS` can be an operational broadcast, while a genuine request to
check documents arrives under a subject made of routing codes such as
`AFEMY - MOMBASA_KENYA - ONE(SINF87558867)`. Classification therefore reads the
full text, and **rule order encodes strength of evidence**:

1. An attached SI + BL pair — the strongest possible signal, nothing overrides it
2. An SI transmittal (`SI - <booking> - ...`, or "please find Shipping instruction for") — settled *before* comparison, because these messages mention the BL in passing
3. Comparison intent (`draft bl`, `amend bl`, `for checking`, `check the details`, `bl matches the si`)
4. Spam
5. Operational reports (`berthing report`, `update summary`, `outstanding bl`, `all pending shipments`) — placed before the weaker keywords so a misleading subject cannot hijack a berthing report
6. Explicit SI requests
7. Automated bot notices (`automated notification`, `no action required`, `rpa bot`)
8. Billing intent — specific phrases plus an invoice carrying a reference number
9. Fallback: general correspondence

Phrase matching uses a custom boundary — "not adjacent to a letter or digit" —
rather than `\b`. These subjects separate words with underscores
(`SI NEEDED_ 5RMY-69379`), and both `\b` and `\w` treat `_` as a word
character, so a naive word-boundary pattern silently fails on exactly this
traffic.

### Extraction: three passes over the text

1. `Key: Value` and `Key | Value` pairs on one line
2. A label on one line with its value on the next, skipping obvious metadata
3. Explicit totals (`No. of Containers`, `Total Gross Wt`), which override table-header ambiguity

`canonical_field()` maps many document-specific labels onto one canonical name,
so `Port of Loading`, `Load Port` and `POL` all resolve to `port_of_loading`.
Placeholders (`N/A`, `TBA`, `TBC`, `nil`, `____MT`, `___ KG`, bare dashes)
become `None` — never a value, so they can never be compared as if real.

### Comparison: absorb cosmetic noise, never invent a defect

- Case and whitespace insensitive
- A trailing UN/LOCODE is stripped, so `NHAVA SHEVA, INDIA (INNSA)` matches `NHAVA SHEVA, INDIA`
- `container_count` is compared as an integer, `gross_weight_kg` as a float with commas stripped
- **If either side is missing, the field is skipped rather than flagged.** Absent data is handled upstream as `NEEDS_REVIEW / missing_value`

### Verdict rules

| Situation | Status | Reason |
|-----------|--------|--------|
| Not a comparison request | `OK` | — |
| Comparison request with no attachments at all | `OK` | Nothing was sent; a thread reply, nothing is wrong |
| Attachments present but the SI/BL pair is incomplete | `NEEDS_REVIEW` | `missing_attachment` |
| A document cannot be read | `NEEDS_REVIEW` | `unreadable` |
| The "BL" is an invoice, packing list or certificate | `NEEDS_REVIEW` | `wrong_doc_type` |
| A required field is absent on either document | `NEEDS_REVIEW` | `missing_value` |
| All present fields match | `OK` | — |
| One or more fields differ | `MISMATCH` | fields listed in `defect_fields` |

### AI layer resilience

`GEMINI_MODEL` pins a model; unset, `ai_service` walks a candidate list and
advances on a "model not found" reply, caching the first model that answers.
Transient 503 / UNAVAILABLE errors are retried with backoff. Any failure
degrades to a predictable payload rather than propagating — the dashboard keeps
showing the deterministic verdict.

This is not theoretical: the default model was retired for new API keys
mid-project and the fallback kept the app working.

---

## 🖥️ Dashboard

The Streamlit dashboard is organised so it reads in the same order the system
works — the engine decides, then the AI explains:

1. **Inbox overview** in the sidebar — totals from the last full run, and
   filters by category and status, so a defect case is two clicks away instead
   of a scan through 520 raw ids
2. **Email** — sender, subject, category, body
3. **Analysis Result** — the deterministic verdict, first on the page
4. **Metrics and detected discrepancies** — the authoritative field list
5. **Documents and the field-by-field comparison table** — SI and BL values side by side
6. **AI Verification Explanation** — the differences in operator language, plus a recommended next step
7. **AI cross-check of the email intent** — an independent second opinion on the category
8. **Review details and the raw technical result** — the exact JSON that goes into the submission

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

**214 tests**, organised by the component they protect:

| File | Covers |
|------|--------|
| `test_extractor.py` | Label aliasing, placeholder handling, numeric parsing, all three extraction passes |
| `test_comparator.py` | LOCODE stripping, case/space insensitivity, and that a missing value is skipped rather than flagged |
| `test_classifier.py` | Every classification rule, the precedence order, the underscore boundary case, and a dataset-wide sanity check |
| `test_pipeline.py` | Every verdict path, including all four `NEEDS_REVIEW` reasons, via in-memory fakes |
| `test_document_reader.py` | Real bundle attachments including XLSX, and the unreadable-document failure mode |
| `test_ai_service.py` | Model override and fallback, graceful degradation, `.env` loading, plus live API tests |
| `test_ui_formatting.py` | Display formatting, including a test asserting the raw mixed-type case genuinely fails |

Tests that call the live Gemini API are skipped automatically when
`GEMINI_API_KEY` is not set, so the suite stays green without credentials.

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

## 🧱 Challenges Faced

### 1. The subject line is deliberately misleading

Our first classifier keyed on subjects and phrases, and scored macro-F1 0.715.
Reading the emails that fell through showed 53 genuine comparison requests
hiding under routing-code subjects, all containing one body phrase: *"Please
assist to send the draft BL for ⟨ref⟩ for checking asap"*. Meanwhile 45 SI
transmittals were being read as billing queries.

**Resolution:** move the decision to the body and order rules by strength of
evidence. Macro-F1 went from 0.715 to 1.000.

### 2. Fixing one category collapsed another

Broadening the comparison rules did find all 220 comparison emails — and
swallowed all 125 SI transmittals with them, because those messages reference
the BL in passing (`HOUSE BL`, `SURR BL`). Precision on comparisons fell to
0.64 and the SI category dropped to zero F1. The overall score went *down*,
from 0.9145 to 0.9098.

**Resolution:** recognise the SI transmittal template *before* the comparison
rules read the text. A test now pins that ordering so the regression cannot
come back.

### 3. One over-broad keyword damaged three categories

The bare word `invoice`, matched anywhere in a body, produced 67 false
positives — stealing emails from SI requests, general correspondence and spam
simultaneously. It was found by attributing every prediction to the specific
rule that fired, rather than by staring at the data.

**Resolution:** billing detection now requires real billing intent — cancel
invoice, charges, freight, or an invoice carrying a reference number.

### 4. Escalating too much is its own failure

Early on the pipeline escalated 58 emails for human review when only 20
genuinely needed it — escalation precision 0.345. Burying a reviewer in false
alarms defeats the purpose of asking for help.

**Resolution:** separate two situations that look identical. "No attachments at
all" is a thread reply — nothing was sent, nothing is wrong. "An attachment is
here but half the pair is missing" genuinely needs chasing. Precision went to
1.000 and the reliability F1 from 0.305 to 0.919, at the cost of recall
dropping to 0.850 — a trade we took deliberately and report openly.

### 5. A model that exists but does not answer

`models.list()` returned `gemini-2.5-flash-lite`, so it looked available. The
first real call answered **404: "no longer available to new users. Please
update your code to use models/gemini-3.5-flash-lite"**. Listing a model does
not mean it will serve you.

**Resolution:** the candidate chain absorbed the failure automatically and the
app kept working; the default now leads with the model the API itself
recommends. The caveat is documented in `discover_models()` so nobody repeats
the mistake.

### 6. Silent failures in the plumbing

Two bugs that produced no error message and would have cost hours during a
demo: `python-dotenv` was a declared dependency but `load_dotenv()` was never
called, so a local `.env` was ignored entirely; and the comparison table mixed
strings, ints and floats in one column, making pyarrow raise on every single
render while Streamlit quietly papered over it.

**Resolution:** explicit `.env` loading anchored to the repository root, and a
display formatter that renders every value as text. Both are covered by tests
now — including one that asserts the raw mixed-type case *does* fail, so the
reason for the conversion stays documented.

---

## 🗺️ Future Roadmap

### Near term

- **OCR for scanned documents.** Three emails in the dataset carry image-only
  PDFs with no text layer. They are correctly escalated today, but never
  compared. PyMuPDF already renders pages to images; the missing piece is
  Tesseract or a vision model, feeding results through the same deterministic
  comparison so the architecture principle holds.
- **Close the human-in-the-loop.** Today the system escalates with a reason.
  Next it should let an operator confirm or correct a verdict and have the
  report update, turning review outcomes into an audit trail.
- **Evidence for every review reason.** `missing_value` cases already persist
  the extracted data; `unreadable` and `wrong_doc_type` should carry the same
  supporting context.

### Medium term

- **Confidence-based routing** — surface *how certain* an extraction was, so
  borderline cases can be prioritised rather than treated identically.
- **Amendment drafting** — given a mismatch, propose the corrected BL text for
  the operator to approve, instead of only naming the differing fields.
- **Learning from corrections** — feed operator overrides back as new label
  aliases, so the extraction vocabulary grows from real usage.

### Production readiness

- **Real mailbox integration** — the data source is already swappable via
  `SHIPGUARD_DATA` (folder or HTTP); an IMAP/Graph connector is the natural next
  adapter.
- **Queue-based processing** with visible retries for failed documents.
- **Metrics and alerting** on defect rate and escalation volume, so a drift in
  document quality is noticed rather than absorbed.

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
