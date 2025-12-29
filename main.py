from fastapi import FastAPI
import re

app = FastAPI()

MARKDOWN_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')
ANGLE_URL = re.compile(r'<(https?://[^>]+)>')

def fix_text(text: str) -> str:
    text = MARKDOWN_LINK.sub(r'\2', text)
    text = ANGLE_URL.sub(r'\1', text)
    return text

def sanitize(obj):
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    if isinstance(obj, str):
        return fix_text(obj)
    return obj

@app.post("/validate-job-json")
def validate_job_json(payload: dict):
    cleaned = sanitize(payload)
    return cleaned
