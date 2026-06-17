"""
Vercel Serverless Function 入口
路由: /api/screen, /api/references, /api/config, /api/analyze
"""

import os
import sys

# 确保项目根目录在 Python path 中
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from flask import Flask, request, jsonify
from engine import ScreeningEngine
from references import REFERENCES
from config import AI_PROVIDER, is_configured, PROVIDERS
from chart_analyzer import ChartAnalyzer

app = Flask(__name__)


@app.route("/api/screen", methods=["POST", "OPTIONS"])
def screen():
    if request.method == "OPTIONS":
        resp = jsonify()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    data = request.get_json(silent=True) or {}
    engine = ScreeningEngine()
    result = engine.run_full_screening(data)

    resp = jsonify(result)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/references", methods=["GET"])
def references():
    resp = jsonify(REFERENCES)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/config", methods=["GET"])
def config():
    resp = jsonify({
        "provider": AI_PROVIDER,
        "configured": is_configured(),
        "provider_name": PROVIDERS.get(AI_PROVIDER, {}).get("name", AI_PROVIDER),
    })
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/api/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        resp = jsonify()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    symbol = request.form.get("symbol", "").strip()
    provider = request.form.get("provider", AI_PROVIDER)
    timeframes = request.form.getlist("timeframes")

    if not symbol:
        resp = jsonify({"error": "请输入标的代码", "opportunities": [], "warnings": []})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    # 读取上传的图片
    image_data = []
    files = request.files.getlist("images")
    for f in files:
        content = f.read()
        if content:
            mime = f.content_type or "image/png"
            image_data.append((content, mime))

    if not image_data:
        resp = jsonify({"error": "请至少上传一张K线截图", "opportunities": [], "warnings": []})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    # 临时切换 provider
    import config
    original_provider = config.AI_PROVIDER
    config.AI_PROVIDER = provider

    try:
        analyzer = ChartAnalyzer()
        result = analyzer.analyze(image_data, timeframes, symbol)
    finally:
        config.AI_PROVIDER = original_provider

    resp = jsonify(result)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp
