from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Any
import json
import re

# =========================================================
# FastAPI App
# =========================================================

app = FastAPI(
    title="Job Listing JSON Validator",
    version="1.0.0"
)

# ---------------------------------------------------------
# CORS (允许 GPT / WordPress / 浏览器 调用)
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# Regex Rules (STRICT)
# =========================================================

# Markdown link: [text](https://example.com)
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")

# =========================================================
# Utility Functions
# =========================================================

def extract_plain_url(text: str) -> str:
    """
    If text contains Markdown URL, extract the raw URL only.
    """
    match = MARKDOWN_LINK_PATTERN.search(text)
    return match.group(2) if match else text


def fix_html_links(html: str) -> str:
    """
    Replace Markdown links inside HTML with proper <a href="...">.
    """
    def replacer(match):
        label, url = match.groups()
        return (
            f'<a href="{url}" target="_blank" '
            f'rel="noopener noreferrer">{label}</a>'
        )

    return MARKDOWN_LINK_PATTERN.sub(replacer, html)


def fix_value(value: Any) -> Any:
    """
    Recursively walk the JSON and:
    - Replace Markdown URLs in strings
    - Fix HTML links
    """
    if isinstance(value, str):
        # Fix Markdown inside HTML
        if "<a" in value or "<p" in value or "<li" in value:
            value = fix_html_links(value)

        # Fix plain Markdown URL
        if MARKDOWN_LINK_PATTERN.search(value):
            return extract_plain_url(value)

        return value

    if isinstance(value, list):
        return [fix_value(v) for v in value]

    if isinstance(value, dict):
        return {k: fix_value(v) for k, v in value.items()}

    return value


def contains_markdown(value: Any) -> bool:
    """
    Final safety check: NO Markdown allowed anywhere.
    """
    if isinstance(value, str):
        return bool(MARKDOWN_LINK_PATTERN.search(value))

    if isinstance(value, list):
        return any(contains_markdown(v) for v in value)

    if isinstance(value, dict):
        return any(contains_markdown(v) for v in value.values())

    return False


# =========================================================
# API Endpoints
# =========================================================

@app.get("/")
def health_check():
    """
    Simple health check for Render / browser.
    """
    return {"status": "ok", "service": "job-json-validator"}


@app.post("/validate-job-json")
def validate_and_fix_job_json(payload: dict):
    """
    Validate + auto-fix Job Listing JSON.
    - Removes Markdown URLs
    - Ensures JSON is safe for WordPress import
    """

    # Basic structure validation
    if "jobs" not in payload or not isinstance(payload["jobs"], list):
        raise HTTPException(
            status_code=422,
            detail="Invalid JSON: missing 'jobs' array"
        )

    # Auto-fix
    fixed_payload = fix_value(payload)

    # Final hard stop: NO Markdown allowed
    if contains_markdown(fixed_payload):
        raise HTTPException(
            status_code=422,
            detail="Markdown URL detected after auto-fix. JSON rejected."
        )

    # Final JSON serialization check
    try:
        json.dumps(fixed_payload, ensure_ascii=False)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"JSON serialization failed: {str(e)}"
        )

    return {
        "status": "ok",
        "fixed_json": fixed_payload
    }


