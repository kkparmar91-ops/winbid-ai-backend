# Deploy Python Backend FREE on Railway.app

## 5-Minute Setup

### Step 1: Create GitHub Repo

1. Go to https://github.com and sign in
2. Click "New repository"
3. Name it: `winbid-ai-backend`
4. Click "Create repository"
5. Upload these 3 files:
   - main.py
   - requirements.txt
   - Procfile

### Step 2: Deploy to Railway

1. Go to: https://railway.app
2. Click "Start a New Project"
3. Click "Deploy from GitHub repo"
4. Select your `winbid-ai-backend` repo
5. Railway will auto-detect Python and deploy!

### Step 3: Add Environment Variables

In Railway dashboard → Your Project → Variables → Add:

| Name | Value |
|------|-------|
| `GEMINI_API_KEY` | Your Gemini API key (AIza...) |
| `API_SECRET` | winbid_secret_2026 |

### Step 4: Get Your URL

After deploy, click your project → Settings → Domains
You'll get a URL like: `https://winbid-ai-backend.up.railway.app`

### Step 5: Update config.php

In `d:\Tender\config\config.php`, update:
```php
define('PYTHON_BACKEND_URL', 'https://winbid-ai-backend.up.railway.app');
```

### Step 6: Upload config.php to HostEasy

Upload updated `config/config.php` and `api/upload_tender_simple_v2.php` to server.

### Step 7: Test!

Upload a tender PDF and watch it auto-fill! 🎉

---

## Cost

Railway Free Tier:
- $5 free credits/month
- More than enough for your use
- No credit card required to start

---

## Alternative: Render.com (Also FREE)

1. Go to: https://render.com
2. New → Web Service
3. Connect GitHub repo
4. Add environment variables
5. Deploy!

Render free tier keeps service alive and works great.
