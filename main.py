"""
WinBid AI Backend
- Accepts PDF upload from PHP (HostEasy)
- Extracts text with pdfplumber
- Calls Gemini AI via REST API (no SDK - more compatible)
- Returns JSON to PHP
Deploy FREE on Render.com
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import os
import json
import re
import tempfile
import requests
from functools import wraps

# OCR imports (fallback for scanned PDFs)
try:
    from pdf2image import convert_from_path
    import pytesseract
    OCR_AVAILABLE = True
    print("✅ OCR support available")
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️  OCR not available")

app = Flask(__name__)
CORS(app, origins=["https://winbid.dureka.co.in", "http://localhost", "*"])

# ── Environment variables (set in Render dashboard) ───────────────────────────
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
API_SECRET     = os.environ.get('API_SECRET', 'winbid_secret_2026')

print(f"✅ Gemini key: {'configured (' + GEMINI_API_KEY[:10] + '...)' if GEMINI_API_KEY else 'NOT SET'}")

# Gemini REST API URL (no SDK needed)
# AI Provider URLs
GEMINI_URL      = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
GROQ_URL        = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL  = "https://openrouter.ai/api/v1/chat/completions"

# API Keys from environment
GROQ_API_KEY        = os.environ.get('GROQ_API_KEY', '')
OPENROUTER_API_KEY  = os.environ.get('OPENROUTER_API_KEY', '')

def call_ai(prompt):
    """Try all available AI providers in order"""

    # 1. OpenRouter (free, no credit card, 20+ models)
    if OPENROUTER_API_KEY:
        try:
            r = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://winbid.dureka.co.in",
                    "X-Title": "WinBid"
                },
                json={
                    "model": "meta-llama/llama-3.1-8b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2048
                },
                timeout=60
            )
            print(f"OpenRouter: HTTP {r.status_code}")
            if r.status_code == 200:
                text = r.json()['choices'][0]['message']['content']
                print("✅ OpenRouter succeeded")
                return text
            print(f"OpenRouter error: {r.text[:200]}")
        except Exception as e:
            print(f"OpenRouter failed: {e}")

    # 2. Groq (free tier)
    if GROQ_API_KEY:
        try:
            r = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": "llama3-70b-8192", "messages": [{"role": "user", "content": prompt}], "max_tokens": 2048},
                timeout=60
            )
            print(f"Groq: HTTP {r.status_code}")
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content']
            print(f"Groq error: {r.text[:200]}")
        except Exception as e:
            print(f"Groq failed: {e}")

    # 3. Gemini fallback
    if GEMINI_API_KEY:
        try:
            key = GEMINI_API_KEY
            r = requests.post(
                f"{GEMINI_URL}?key={key}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.2}},
                timeout=90
            )
            if r.status_code == 200:
                return r.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Gemini failed: {e}")

    return None

# ── Auth decorator ─────────────────────────────────────────────────────────────
def require_secret(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = request.headers.get('X-API-Secret') or request.form.get('api_secret')
        if secret != API_SECRET:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def health():
    """Health check - visit URL to confirm deployment worked"""
    return jsonify({
        'status':  'ok',
        'service': 'WinBid AI Backend',
        'gemini':  'configured' if GEMINI_API_KEY else 'NOT SET - add GEMINI_API_KEY in environment variables',
        'version': '1.0.0'
    })


@app.route('/debug', methods=['GET'])
def debug():
    """Show config and test all auth methods"""
    key = GEMINI_API_KEY
    result = {
        'key_set': bool(key),
        'key_preview': (key[:6] + '...' + key[-4:]) if len(key) > 10 else key,
        'key_length': len(key),
        'key_starts_with': key[:5] if key else 'EMPTY',
    }

    # Test all 3 methods
    methods = [
        ('query_param',    f"{GEMINI_URL}?key={key}", {}),
        ('bearer_token',   GEMINI_URL, {"Authorization": f"Bearer {key}"}),
        ('x-goog-api-key', GEMINI_URL, {"x-goog-api-key": key}),
    ]

    results = {}
    body = {"contents": [{"parts": [{"text": "say: OK"}]}],
            "generationConfig": {"maxOutputTokens": 10}}

    for name, url, extra_headers in methods:
        try:
            headers = {"Content-Type": "application/json", **extra_headers}
            r = requests.post(url, headers=headers, json=body, timeout=15)
            results[name] = {
                'http_code': r.status_code,
                'working': r.status_code == 200,
                'response': r.text[:150]
            }
        except Exception as e:
            results[name] = {'error': str(e)}

    result['auth_methods'] = results
    return jsonify(result)


@app.route('/test_text', methods=['POST'])
@require_secret
def test_text():
    """Test AI with hardcoded sample text - no PDF needed"""
    sample = """
    NOTICE INVITING TENDER - NIT No. PWD/2026/1234
    Construction of 4-Lane Bridge over River Yamuna, Pune Maharashtra
    Estimated Cost: Rs. 15,50,00,000. EMD: Rs. 15,50,000
    Last Date: 15th September 2026. Opening Date: 16th September 2026
    Department: Public Works Department, Maharashtra
    """
    try:
        extracted = extract_with_gemini(sample)
        if extracted:
            return jsonify({'success': True, 'data': extracted})
        return jsonify({'success': False, 'error': 'AI returned None'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/extract', methods=['POST'])
@require_secret
def extract_tender():
    """Main endpoint: PDF → text → AI → JSON"""

    # 1. Validate file
    if 'pdf' not in request.files:
        return jsonify({'success': False, 'error': 'No PDF file in request'}), 400

    pdf_file = request.files['pdf']

    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Only PDF files allowed'}), 400

    tmp_path = None
    try:
        # 2. Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            pdf_file.save(tmp.name)
            tmp_path = tmp.name

        size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        print(f"📄 PDF: {pdf_file.filename} ({size_mb:.2f} MB)")

        # 3. Extract text
        raw_text = extract_pdf_text(tmp_path)
        print(f"📝 Extracted: {len(raw_text)} chars")

        if not raw_text or len(raw_text.strip()) < 30:
            return jsonify({
                'success': False,
                'error': 'Could not extract text. PDF may be scanned/image-based.'
            }), 400

        # 4. AI extraction
        if not GEMINI_API_KEY:
            return jsonify({
                'success': False,
                'error': 'GEMINI_API_KEY not set in environment variables'
            }), 500

        print("🤖 Calling Gemini...")
        extracted = extract_with_gemini(raw_text)

        if not extracted:
            return jsonify({
                'success': False,
                'error': 'AI extraction failed'
            }), 500

        print(f"✅ Done: {extracted.get('title', 'No title')}")

        return jsonify({
            'success':     True,
            'data':        extracted,
            'text_length': len(raw_text),
            'raw_text':    raw_text[:50000]
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Helpers ────────────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_path):
    """Extract text using pdfplumber, with OCR fallback for scanned PDFs"""
    parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"📃 {len(pdf.pages)} pages")
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text and len(text.strip()) > 10:
                    parts.append(text)
                else:
                    words = page.extract_words()
                    if words:
                        word_text = ' '.join([w['text'] for w in words])
                        if len(word_text.strip()) > 10:
                            parts.append(word_text)
                if i >= 29:
                    break
    except Exception as e:
        print(f"pdfplumber error: {e}")

    result = '\n'.join(parts).strip()
    print(f"Extracted {len(result)} chars with pdfplumber")

    # OCR fallback for scanned PDFs
    if len(result) < 50 and OCR_AVAILABLE:
        print("⚠️  Low text, trying OCR...")
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=10, dpi=150)
            ocr_parts = []
            for img in images:
                ocr_text = pytesseract.image_to_string(img, lang='eng')
                if ocr_text.strip():
                    ocr_parts.append(ocr_text)
            result = '\n'.join(ocr_parts).strip()
            print(f"OCR extracted {len(result)} chars")
        except Exception as e:
            print(f"OCR error: {e}")

    return result


def extract_with_gemini(raw_text):
    """Extract tender info using any available AI provider"""
    text = raw_text[:100000]
    prompt = f"""You are an expert tender analysis AI. Extract key information from this tender document.

Return ONLY a valid JSON object with these keys (null if not found):
{{
  "title": "Full tender/project title",
  "tender_no": "Tender/NIT/RFP number",
  "department": "Issuing department/organization",
  "location": "Project location/state",
  "work_description": "Scope of work",
  "estimated_cost": "Project cost with currency",
  "emd_amount": "EMD/Earnest Money amount",
  "last_date": "Last submission date YYYY-MM-DD",
  "open_date": "Opening date YYYY-MM-DD",
  "eligibility": "Eligibility criteria",
  "documents_required": "Required documents list",
  "technical_criteria": "Technical qualifications",
  "financial_criteria": "Financial qualifications",
  "contact_info": "Contact details",
  "ai_summary": "3-sentence executive summary"
}}
TENDER TEXT:
{text}
Return ONLY the JSON. No markdown, no explanation."""

    try:
        ai_text = call_ai(prompt)
        if not ai_text:
            raise Exception("All AI providers failed")
        ai_text = re.sub(r'```json\s*', '', ai_text)
        ai_text = re.sub(r'```\s*', '', ai_text).strip()
        return json.loads(ai_text)
    except json.JSONDecodeError as e:
        raise Exception(f"JSON parse failed: {e}")
    except Exception as e:
        print(f"AI error: {e}")
        raise


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
