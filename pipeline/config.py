import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
REQUEST_TIMEOUT = 60

# Generation profile for a classification task
TEMPERATURE = 0.0
TOP_P = 1.0
MAX_OUTPUT_TOKENS = 120
THINKING_LEVEL = "minimal"

MAX_TICKET_CHARS = 2000

DATA_FILE = ROOT / "data" / "tickets.jsonl"
RESULTS_DIR = ROOT / "results"
PRICES_FILE = ROOT / "prices.json"
REPORT_FILE = ROOT / "docs" / "reporte_metricas.md"
