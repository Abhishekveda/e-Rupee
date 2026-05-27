# How to Run e₹ Bridge in VS Code

## One-time setup

**1. Open the project**
```
File → Open Folder → select the E-Rupee folder
```

**2. Open the terminal in VS Code**
```
Terminal → New Terminal   (or press Ctrl + ` )
```

**3. Install Python dependencies**
```bash
cd backend
pip install -r requirements.txt
```

If pip not found, try:
```bash
python -m pip install -r requirements.txt
```

---

## Every time you want to run the demo

**In the VS Code terminal:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

You will see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

**Then open your browser and go to:**
```
http://localhost:8000
```

The demo page opens immediately. ✓

---

## Shortcut — add a Run button in VS Code

Create a file `.vscode/tasks.json` in your project root:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Run e₹ Bridge",
      "type": "shell",
      "command": "cd backend && uvicorn app.main:app --reload --port 8000",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "new" }
    }
  ]
}
```

Then press **Ctrl+Shift+B** to start the server instantly.

---

## Stop the server

Press **Ctrl + C** in the terminal.

---

## Technical API docs (for engineers only)

```
http://localhost:8000/api-docs
```

---

## Windows specific

If you get "uvicorn not found":
```bash
python -m uvicorn app.main:app --reload --port 8000
```

If you use Anaconda, open **Anaconda Prompt** instead of VS Code terminal:
```bash
cd C:\path\to\E-Rupee\backend
uvicorn app.main:app --reload --port 8000
```
