"""
Vercel Serverless Function 入口
路由: /api/screen, /api/references, /api/config
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
