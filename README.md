# IC3 Admin Web Controller

FastAPI backend for the IC3 Multi-Channel admin panel.
**Does not re-implement business logic** – it calls `core.CaseManager` and `core.ContentManager` directly.

---

## Files

```
web_controller/
├── main.py          # FastAPI app – all route definitions
├── auth.py          # JWT creation / verification helpers
├── models.py        # Pydantic request/response models
├── utils.py         # Pagination, serialisation, audit log helper
├── requirements.txt # Python dependencies
└── README.md
```

---

## Running locally

```bash
# 1. Install deps
pip install -r web_controller/requirements.txt

# 2. Set env vars (or create a .env and load with python-dotenv)
export DB_HOST=localhost
export DB_NAME=weiquan_bot
export DB_USER=postgres
export DB_PASSWORD=your_password
export WEB_SECRET_KEY=supersecret
export WEB_ADMIN_TOKEN=myadmintoken
export CORS_ORIGINS=http://localhost:3000

# 3. Start server
uvicorn web_controller.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs

---

## Authentication flow

```
POST /api/auth/login   { "token": "<WEB_ADMIN_TOKEN>" }
→ { "access_token": "<JWT>", ... }

All other endpoints require:
  Authorization: Bearer <JWT>
```

---

## API summary

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Exchange admin token for JWT |
| GET  | `/api/auth/me` | Inspect current identity |
| GET  | `/api/templates` | List templates (`?channel=telegram`) |
| GET  | `/api/templates/{key}?channel=` | Get single template |
| POST | `/api/templates` | Create template |
| PUT  | `/api/templates/{key}` | Update template + auto-invalidate cache |
| DELETE | `/api/templates/{key}?channel=` | Delete template |
| POST | `/api/templates/preview` | Render template with variables |
| POST | `/api/templates/cache/refresh` | Clear in-memory cache |
| GET  | `/api/templates/stats` | Per-channel counts + recent updates |
| GET  | `/api/cases` | Paginated cases (`?page=&limit=&status=&channel=`) |
| GET  | `/api/cases/{case_id}` | Full case detail with evidence + history |
| PUT  | `/api/cases/{case_id}/status` | Update case status |
| GET  | `/api/channels/config` | All channel config entries |
| PUT  | `/api/channels/{type}/config` | Upsert config keys for a channel |
| GET  | `/api/dashboard/stats` | Aggregate counts for dashboard |
| GET  | `/health` | Liveness probe |

---

## Adding a new route

1. Define request/response models in `models.py`
2. Add the endpoint function in `main.py`
3. Call `_case_manager` or `_content_manager` as needed
4. Add an audit log entry via `utils.write_audit_log()` for write operations

---

## Docker (optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r web_controller/requirements.txt
CMD ["uvicorn", "web_controller.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
"# -"  
