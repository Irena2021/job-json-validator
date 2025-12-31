from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import re
from typing import Any, Dict, List

app = FastAPI(title="Job JSON Validator")

# ------------------------
# 1) 输入模型：只收一个字符串
# ------------------------
class ValidateRequest(BaseModel):
    raw_json: str

# ------------------------
# 2) URL/Markdown 清洗
# ------------------------
def fix_markdown_links(text: str) -> str:
    # [text](https://url) -> https://url
    return re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\2", text)

def fix_angle_bracket_urls(text: str) -> str:
    # <https://url> -> https://url
    return re.sub(r"<(https?://[^>]+)>", r"\1", text)

def fix_html_anchor_links(text: str) -> str:
    # href="[https://url](https://url)" -> href="https://url"
    return re.sub(r'href="\[(https?://[^\]]+)\]\(\1\)"', r'href="\1"', text)

def clean_all_urls(text: str) -> str:
    text = fix_markdown_links(text)
    text = fix_angle_bracket_urls(text)
    text = fix_html_anchor_links(text)
    return text

# ------------------------
# 3) 结构校验（轻量，不阻断）
# ------------------------
def validate_structure(data: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []

    if not isinstance(data, dict):
        return ["root is not an object"]

    if data.get("category_slug") != "joblisting":
        warnings.append("category_slug should be 'joblisting'")

    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        warnings.append("jobs must be an array")
        return warnings

    for i, job in enumerate(jobs):
        if not isinstance(job, dict):
            warnings.append(f"jobs[{i}] is not an object")
            continue

        group = job.get("group_slug", f"jobs[{i}]")

        for lang in ["zh", "en"]:
            lang_obj = job.get(lang)
            if not isinstance(lang_obj, dict):
                warnings.append(f"{group} {lang}: missing language object")
                continue

            # slug
            slug = lang_obj.get("slug")
            if not isinstance(slug, str) or not slug.strip():
                warnings.append(f"{group} {lang}: missing/invalid slug")

            # acf.job_link
            acf = lang_obj.get("acf")
            if not isinstance(acf, dict):
                warnings.append(f"{group} {lang}: missing/invalid acf")
                continue

            job_link = acf.get("job_link", "")
            if not isinstance(job_link, str) or not job_link.startswith("https://"):
                warnings.append(f"{group} {lang}: acf.job_link must be plain https URL")

            if any(ch in job_link for ch in ["[", "]", "(", ")", "<", ">"]):
                warnings.append(f"{group} {lang}: acf.job_link contains illegal characters")

    return warnings

# ------------------------
# 4) API：validate + auto-fix
# ------------------------
@app.post("/validate-job-json")
async def validate_and_fix(payload: ValidateRequest):
    # 先清洗，再尝试 parse
    cleaned_text = clean_all_urls(payload.raw_json)

    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=200,
            content={
                "status": "invalid_json",
                "message": "JSON syntax error after auto-fix",
                "error": str(e),
                "cleaned_preview": cleaned_text[:1200],
            },
        )

    warnings = validate_structure(data)

    return {
        "status": "ok" if not warnings else "fixed_with_warnings",
        "warnings": warnings,
        "fixed_json": data,
    }

@app.get("/")
def root():
    return {"status": "Job JSON Validator is running"}
