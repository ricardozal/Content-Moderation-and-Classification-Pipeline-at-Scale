import json

from pipeline import config


def load_tickets(path=config.DATA_FILE, limit=None):
    tickets = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            tickets.append({
                "id": row["id"],
                "text": row["text"][: config.MAX_TICKET_CHARS],
                "expected_category": row.get("expected_category"),
                "expected_priority": row.get("expected_priority"),
            })
    return tickets[:limit] if limit else tickets
