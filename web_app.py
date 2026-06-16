"""
价格行为学交易筛查系统 - Web服务
"""

import os
import sys
import json
import tempfile

if sys.platform == "win32":
    os.system("")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from engine import ScreeningEngine
from references import REFERENCES
from config import AI_PROVIDER, is_configured, PROVIDERS
from chart_analyzer import ChartAnalyzer

app = FastAPI(title="价格行为学交易筛查系统")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/references", response_class=JSONResponse)
async def get_references():
    return REFERENCES


@app.get("/api/config", response_class=JSONResponse)
async def get_config():
    return {
        "provider": AI_PROVIDER,
        "configured": is_configured(),
        "provider_name": PROVIDERS.get(AI_PROVIDER, {}).get("name", AI_PROVIDER),
    }


@app.get("/analyze", response_class=HTMLResponse)
async def analyze_page(request: Request):
    return templates.TemplateResponse("analyze.html", {"request": request})


@app.post("/api/analyze", response_class=JSONResponse)
async def analyze_charts(
    symbol: str = Form(...),
    provider: str = Form("openai"),
    images: list[UploadFile] = File(...),
    timeframes: list[str] = Form(...),
):
    # 读取图片
    image_data = []
    for img_file in images:
        content = await img_file.read()
        mime = img_file.content_type or "image/png"
        image_data.append((content, mime))

    # 临时覆盖provider
    import config
    original_provider = config.AI_PROVIDER
    config.AI_PROVIDER = provider

    try:
        analyzer = ChartAnalyzer()
        result = analyzer.analyze(image_data, timeframes, symbol)
        return JSONResponse(result)
    finally:
        config.AI_PROVIDER = original_provider


@app.post("/screen", response_class=HTMLResponse)
async def screen(request: Request):
    form = await request.form()
    data = dict(form)

    engine = ScreeningEngine()
    result = engine.run_full_screening(data)

    return templates.TemplateResponse("result.html", {"request": request, "r": result})


if __name__ == "__main__":
    import uvicorn
    print("\n  价格行为学交易筛查系统 已启动")
    print("  浏览器访问: http://127.0.0.1:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
