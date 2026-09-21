# 🚢 ShipGuard

### AI-Assisted Shipping Document Verification System

ShipGuard is an AI-assisted document verification system designed to help shipping operations teams validate emails and compare Shipping Instructions (SI) against Bills of Lading (BL).

The system combines a deterministic verification engine with Gemini AI to provide reliable document validation and human-readable explanations.

---

## 🎯 Problem

Shipping operations involve large volumes of emails and documents.

Important information such as:

- Shipper
- Consignee
- Notify Party
- Port of Loading
- Port of Discharge
- Container Count
- Gross Weight

can differ between a Shipping Instruction and a Bill of Lading.

Manually checking these documents is time-consuming and can lead to missed discrepancies.

ShipGuard automates this process by identifying relevant emails, extracting document information, comparing required fields, and explaining detected issues.

---

## 💡 Solution

ShipGuard provides an end-to-end workflow:

```text
Incoming Shipping Email
        ↓
Email Classification
        ↓
Document Detection
        ↓
SI / BL Data Extraction
        ↓
Deterministic Field Comparison
        ↓
Validation Result
        ↓
Gemini AI Explanation
        ↓
Human-Readable Result

The deterministic verification engine remains responsible for the final validation result.

Gemini AI is used to understand email intent and explain the verification results in natural language.

✨ Key Features
📧 Email Classification

ShipGuard classifies incoming emails into five categories:

BL_COMPARISON
SI_REQUEST
INVOICE_QUERY
GENERAL
SPAM
📄 Shipping Document Detection

The system automatically identifies:

Shipping Instructions (SI)
Bills of Lading (BL)

It can also detect unsupported or incorrect document types.

🔍 Seven-Field Document Comparison

ShipGuard compares the following required fields:

Field	Description
shipper	Shipping party
consignee	Consignee
notify_party	Notify party
port_of_loading	Port where cargo is loaded
port_of_discharge	Destination discharge port
container_count	Number of containers
gross_weight_kg	Gross cargo weight
✅ Verification Statuses

For document comparisons, ShipGuard produces one of three statuses:

OK

All required values available for comparison match.

MISMATCH

One or more document fields contain different values.

The system also identifies the specific fields that differ.

NEEDS_REVIEW

The system cannot safely complete the comparison.

This can occur when:

Required attachment is missing
Document type is incorrect
Document is unreadable
Required value is missing

ShipGuard uses NEEDS_REVIEW instead of guessing when the available information is insufficient.

🤖 AI Integration

ShipGuard uses Google Gemini as an AI assistant.

Gemini performs two main tasks.

1. Email Understanding

Gemini analyzes the email and provides:

Email category
Short summary
Confidence score
2. Verification Explanation

After the deterministic engine completes the document comparison, Gemini explains the result in human-readable language.

For example:

SI shows PORT KLANG (WESTPORT), MALAYSIA
while BL shows RUGAO/NANTONG/SHANGHAI, CHINA.

Gemini can also provide a recommended next step for the shipping operator.

Important Architecture Principle

Gemini does not determine whether documents match.

The deterministic verification engine makes the final validation decision.

              ┌─────────────────────┐
              │   Shipping Email    │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Email Classification│
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Document Extraction │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Deterministic       │
              │ SI / BL Comparison  │
              └──────────┬──────────┘
                         │
                ┌────────┴────────┐
                │                 │
                ▼                 ▼
             Result           Comparison
                │                 │
                └────────┬────────┘
                         ▼
              ┌─────────────────────┐
              │    Gemini AI        │
              │ Explanation Layer   │
              └──────────┬──────────┘
                         │
                         ▼
              Human-readable result

This architecture reduces the risk of an AI model changing the actual verification result.

🧠 Intelligent Review Handling

ShipGuard avoids making assumptions when document information is incomplete.

For example, if the Shipping Instruction does not contain a required gross weight:

Shipping Instruction: —
Bill of Lading: 235550 kg
Validation: NEEDS_REVIEW
Reason: Missing required value

Instead of assuming that the Bill of Lading value is correct, the system requests human review.

🖥️ User Interface

The ShipGuard interface is built with Streamlit.

The dashboard provides:

Email selection
Email content
Attached documents
Analysis result
AI analysis
AI verification explanation
Field-by-field document comparison
Review details
Technical validation information
🛠️ Technology Stack
Frontend / UI
Streamlit
Backend / Processing
Python
Custom deterministic validation pipeline
PDF and document extraction
AI
Google Gemini
google-genai
Data Processing
Pandas
PyMuPDF
pypdf
python-docx
openpyxl
Development
Git
GitHub
VS Code
Deployment
Streamlit Community Cloud
📁 Project Structure
shipguard/
│
├── app.py
├── ai_service.py
├── pipeline.py
├── classifier.py
├── comparator.py
├── extractor.py
├── document_reader.py
├── loader.py
├── normalizer.py
├── processor.py
├── main.py
│
├── submission.py
├── submission.json
├── results.json
│
├── requirements.txt
├── .env.example
├── .gitignore
│
└── sdoc-hackathon-bundle/
    ├── attachments/
    └── inbox/
🚀 Local Installation
1. Clone the repository
git clone https://github.com/Samidjon/shipguard.git
cd shipguard
2. Create a virtual environment

Windows:

python -m venv .venv
.venv\Scripts\Activate.ps1
3. Install dependencies
pip install -r requirements.txt
4. Configure Gemini API

Create a .env file:

GEMINI_API_KEY=your_gemini_api_key_here

Do not commit your real API key to GitHub.

5. Run ShipGuard
streamlit run app.py

The application will open in your browser.

☁️ Live Demo

ShipGuard Live Prototype:

https://shipguard-kjxefg6xu7p8t4iedbwyi3.streamlit.app/

The deployed application runs on Streamlit Community Cloud.

💻 GitHub

Source Code:

https://github.com/Samidjon/shipguard

🔐 Security

API credentials are not stored in the source code.

Local development uses environment variables.

Cloud deployment uses Streamlit Secrets.

The repository contains only:

.env.example

with a placeholder API key.

Real credentials must never be committed to Git.

📊 Dataset

ShipGuard was developed using the provided shipping document hackathon dataset.

The project processes the complete dataset and produces a structured submission containing one result for every email.

The current pipeline processes:

520 emails

The submission output follows the required category and verification status structure.

🏆 Hackathon

Built for the Averis x Monash Hackathon 2026.

The project focuses on applying AI and cloud technologies to shipping operations and document verification.

Core concept

Automate repetitive shipping document verification while keeping the final validation deterministic and transparent.

👥 Project

ShipGuard

AI-Assisted Shipping Document Verification System

Built with:

Python
Streamlit
Google Gemini
Document processing
Deterministic validation
Cloud deployment