from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import re

app = FastAPI(title="Job JSON Validator")

# ---------- URL 清洗规则 ----------

def fix_markdown_links(text: str) -> str:
    """
    把 [text](https://url) → https://url
    """
    pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
    return pattern.sub(r"\2", text)

def fix_angle_bracket_urls(text: str) -> str:
    """
    把 <https://url> → https://url
    """
    pattern = re.compile(r"<(https?://[^>]+)>")
    return pattern.sub(r"\1", text)

def fix_html_anchor_links(text: str) -> str:
    """
    修复 <a href="[https://url](https://url)"> → <a href="https://url">
    """
    pattern = re.compile(
        r'href="\[(https?://[^\]]+)\]\(\1\)"'
    )
    return pattern.sub(r'href="\1"', text)

def clean_all_urls(text: str) -> str:
    """
    统一 URL 清洗入口
    """
    text = fix_markdown_links(text)
    text = fix_angle_bracket_urls(text)
    text = fix_html_anchor_links(text)
    return text

# ---------- 主接口 ----------

@app.post("/validate-job-json")
async def validate_and_fix_job_json(request: Request):
    raw_body = await request.body()

    try:
        raw_text = raw_body.decode("utf-8")
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "Request body is not valid UTF-8"}
        )

    # 第一步：清洗所有 URL（在 JSON parse 之前）
    cleaned_text = clean_all_urls(raw_text)

    # 第二步：尝试解析 JSON
    try:
        data = json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=200,
            content={
                "status": "invalid_json",
                "message": "JSON syntax error after auto-fix",
                "error": str(e),
                "cleaned_preview": cleaned_text[:800]
            }
        )

    # 第三步：结构级校验（非致命）
    warnings = []

    for job in data.get("jobs", []):
        group = job.get("group_slug", "unknown")

        for lang in ["zh", "en"]:
            lang_obj = job.get(lang, {})

            # 校验 slug
            slug = lang_obj.get("slug", "")
            if not slug or not isinstance(slug, str):
                warnings.append(f"{group} {lang}: missing or invalid slug")

            # 校验 job_link
            acf = lang_obj.get("acf", {})
            job_link = acf.get("job_link", "")

            if not job_link.startswith("https://"):
                warnings.append(f"{group} {lang}: job_link is not a plain https URL")

            if "[" in job_link or "(" in job_link or "<" in job_link:
                warnings.append(f"{group} {lang}: job_link still contains illegal characters")

    return {
        "status": "ok" if not warnings else "fixed_with_warnings",
        "warnings": warnings,
        "fixed_json": data
    }

# ---------- Health Check ----------

@app.get("/")
def root():
    return {"status": "Job JSON Validator is running"}
