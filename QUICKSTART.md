# How to Run e₹ Bridge — Step by Step

## The 3-command start

```bash
git clone https://github.com/Abhishekveda/E-Rupee.git
cd E-Rupee/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open your browser at:
```
http://localhost:8000
```

That's it. You see the full demo immediately.

---

## What you get at localhost:8000

- **The live demo page** — user-friendly, works for non-technical audiences
- Select destination country (UAE, Singapore, UK, Canada)
- Enter amount — quick buttons for ₹5k / ₹10k / ₹25k / ₹50k / ₹1 lakh
- Pick purpose (Family / Education / Medical / Business / Travel)
  OR click "✦ Let AI decide" and type in plain English
- The **real AI agent** runs and returns the FEMA code
- Hit "Send Money" — see all 5 steps complete in real time
- Receipt with AI summary

The AI badge shows **"AI Agent: LIVE"** when it's calling the real Python backend.

---

## For the technical API docs

Go to:
```
http://localhost:8000/api-docs
```

This has all the raw API endpoints with "Try it out" buttons.

---

## Run the terminal demo (for technical audiences)

```bash
cd backend
python poc_demo.py
```

Shows all 5 agents running with coloured output — good for showing to engineers.

---

## Windows (Anaconda)

```bash
cd E-Rupee/backend
& "C:\Users\YOUR_NAME\Anaconda3\python.exe" -m pip install -r requirements.txt
& "C:\Users\YOUR_NAME\Anaconda3\python.exe" -m uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000

---

## Common errors

**`ModuleNotFoundError: No module named 'app'`**
Run from the `backend/` directory, not the root.

**`Address already in use`**
Use a different port: `uvicorn app.main:app --reload --port 8001`

**`pip: command not found`**
Use `pip3` or use the full Anaconda path above.
