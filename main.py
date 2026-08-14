"""
WinBid AI Backend
- Accepts PDF upload from PHP (HostEasy)
- Extracts text with pdfplumber
- Calls Gemini AI for structured data
- Returns JSON to PHP
Deploy FREE on Railway.app
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import pdfplumber
import os
import json
import re
import tempfile
from functools import wraps

app = Flask(__name__)

# Allow requests from your HostEasy PHP site
CORS(app, origins=["https://winbid.dureka.co.in", "http://localhost"])

# ── Environment variables (set in Railway dashboard) ──────────────────────────
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
API_SECRET     = os.environ.get('API_SECRET', 'winbid_secret_2026')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print(f"✅ Gemini configured: {GEMINI_API_KEY[:10]}...")
else:
    print("⚠️  GEMINI_API_KEY not set!")

# ── Auth decorator ─────────────────────────────────────────────────────────────
def require_secret(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = (
            request.headers.get('X-API-Secret') or
            request.form.get('api_secret') or
            request.json.get('api_secret') if request.is_json else None
        )
        if secret != API_SECRET:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def health():
    """Health check - visit this URL to confirm deployment worked"""
    return jsonify({
        'status':  'ok',
        'service': 'WinBid AI Backend',
        'gemini':  'configured' if GEMINI_API_KEY else 'NOT CONFIGURED - add GEMINI_API_KEY env variable',
        'version': '1.0.0'
    })


@app.route('/extract', methods=['POST'])
@require_secret
def extract_tender():
    """
    Main endpoint: receive PDF → extract text → AI analysis → return JSON
    Called by: d:/Tender/api/upload_tender_simple_v2.php
    """

    # ── 1. Validate file ──────────────────────────────────────────────────────
    if 'pdf' not in request.files:
        return jsonify({'success': False, 'error': 'No PDF file in request'}), 400

    pdf_file = request.files['pdf']

    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Only PDF files allowed'}), 400

    # ── 2. Save to temp file ──────────────────────────────────────────────────
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            pdf_file.save(tmp.name)
            tmp_path = tmp.name

        file_size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        print(f"📄 PDF received: {pdf_file.filename} ({file_size_mb:.2f} MB)")

        # ── 3. Extract text ───────────────────────────────────────────────────
        raw_text = extract_pdf_text(tmp_path)
        print(f"📝 Extracted text: {len(raw_text)} characters")

        if not raw_text or len(raw_text.strip()) < 30:
            return jsonify({
                'success': False,
                'error':   'Could not extract text. PDF may be scanned/image-based. Try a different PDF.'
            }), 400

        # ── 4. AI extraction ──────────────────────────────────────────────────
        if not GEMINI_API_KEY:
            return jsonify({
                'success': False,
                'error':   'GEMINI_API_KEY not configured in Railway environment variables'
            }), 500

        print("🤖 Calling Gemini AI...")
        extracted = extract_with_gemini(raw_text)

        if not extracted:
            return jsonify({
                'success': False,
                'error':   'AI extraction failed - check Railway logs for details'
            }), 500

        print(f"✅ Extraction complete: {extracted.get('title', 'No title')}")

        return jsonify({
            'success':     True,
            'data':        extracted,
            'text_length': len(raw_text),
            'raw_text':    raw_text[:50000]   # send first 50k chars back to PHP for storage
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        # Always clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Helper functions ───────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: str) -> str:
    """Extract text from PDF using pdfplumber (handles most PDFs well)"""
    text_parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"📃 PDF has {len(pdf.pages)} pages")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                # Limit to first 30 pages to avoid timeout
                if i >= 29:
                    print("⚠️  Truncating at 30 pages")
                    break
    except Exception as e:
        print(f"pdfplumber error: {e}")

    return '\n'.join(text_parts).strip()


def extract_with_gemini(raw_text: str) -> dict:
    """Send text to Gemini and parse structured JSON response"""
    # Limit to ~100k chars to stay within token limits
    text = raw_text[:100000]

    prompt = f"""You are an expert tender analysis AI. Analyze the following government tender document text and extract all key information.

Return ONLY a valid JSON object with these exact keys (use null if not found):
{{
  "title": "Full tender/project title",
  "tender_no": "Tender/NIT/RFP number",
  "department": "Issuing department/organization name",
  "location": "Project location/state",
  "work_description": "Detailed description of work/scope",
  "estimated_cost": "Estimated project cost with currency (e.g. Rs.12,50,00,000)",
  "emd_amount": "EMD/Earnest Money Deposit amount with currency",
  "last_date": "Last date for submission in YYYY-MM-DD format",
  "open_date": "Tender opening date in YYYY-MM-DD format",
  "eligibility": "Eligibility criteria in bullet points",
  "documents_required": "List of required documents",
  "technical_criteria": "Technical qualification criteria",
  "financial_criteria": "Financial qualification criteria (turnover, net worth etc.)",
  "contact_info": "Contact details for queries",
  "ai_summary": "A concise 3-sentence executive summary of this tender"
}}

TENDER DOCUMENT TEXT:
{text}

Return ONLY the JSON object. No explanation, no markdown, no code blocks."""

    try:
        model    = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=2048,
                temperature=0.2,
            )
        )

        ai_text = response.text.strip()

        # Strip markdown code blocks if Gemini added them
        ai_text = re.sub(r'```json\s*', '', ai_text)
        ai_text = re.sub(r'```\s*',     '', ai_text)
        ai_text = ai_text.strip()

        data = json.loads(ai_text)
        return data

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}\nRaw response: {ai_text[:500]}")
        return None
    except Exception as e:
        print(f"Gemini error: {e}")
        return None


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 WinBid AI Backend starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
