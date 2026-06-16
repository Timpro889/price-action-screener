"""
K线图AI读图分析引擎
支持 OpenAI / Claude / 智谱 / 通义千问 / DeepSeek 多模型
统一使用 httpx 直接调用，避免 SDK 版本兼容问题
"""

import base64
import json
import os
import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
from config import (
    AI_PROVIDER, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    ZHIPU_API_KEY, ZHIPU_MODEL,
    DASHSCOPE_API_KEY, QWEN_MODEL,
    DEEPSEEK_API_KEY, DEEPSEEK_MODEL,
    is_configured, _cfg,
)
from prompt_templates import SYSTEM_PROMPT, build_analysis_prompt


def _image_to_base64(image_bytes):
    return base64.b64encode(image_bytes).decode("utf-8")


class ChartAnalyzer:
    def __init__(self):
        self.provider = AI_PROVIDER
        self.timeout = 120.0

    def analyze(self, images, timeframes, symbol):
        """
        分析K线截图

        Args:
            images: list of (bytes, mime_type) 元组
            timeframes: list of str, 对应每张图的时间级别
            symbol: str, 标的代码

        Returns:
            dict: 分析结果
        """
        if not is_configured():
            return {
                "error": f"AI_PROVIDER={self.provider}，但对应的API Key未设置。请编辑 ai_config.json 或设置环境变量。",
                "opportunities": [],
                "warnings": [],
            }

        if not images:
            return {
                "error": "请至少上传一张K线截图",
                "opportunities": [],
                "warnings": [],
            }

        timeframe_info = "、".join(timeframes)
        user_prompt = build_analysis_prompt(symbol, timeframe_info)

        try:
            raw = self._call_ai(user_prompt, images)
            return self._parse_response(raw)
        except Exception as e:
            return {
                "error": f"AI分析失败: {str(e)}",
                "opportunities": [],
                "warnings": [],
                "raw_response": str(e),
            }

    def _call_ai(self, prompt, images):
        if self.provider == "openai":
            return self._call_openai(prompt, images)
        elif self.provider == "claude":
            return self._call_claude(prompt, images)
        elif self.provider == "zhipu":
            return self._call_openai_format(
                prompt, images,
                api_key=_cfg("ZHIPU_API_KEY"),
                model=ZHIPU_MODEL,
                base_url="https://open.bigmodel.cn/api/paas/v4",
            )
        elif self.provider == "qwen":
            return self._call_openai_format(
                prompt, images,
                api_key=_cfg("DASHSCOPE_API_KEY"),
                model=QWEN_MODEL,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        elif self.provider == "deepseek":
            return self._call_openai_format(
                prompt, images,
                api_key=_cfg("DEEPSEEK_API_KEY"),
                model=DEEPSEEK_MODEL,
                base_url="https://api.deepseek.com/v1",
            )
        else:
            raise ValueError(f"不支持的AI_PROVIDER: {self.provider}")

    def _call_openai_format(self, prompt, images, api_key, model, base_url):
        """统一调用 OpenAI 兼容格式的 API（使用 httpx）"""
        content = [{"type": "text", "text": prompt}]
        for img_bytes, mime in images:
            b64 = _image_to_base64(img_bytes)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })

        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "max_tokens": 4096,
        }

        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _call_openai(self, prompt, images):
        return self._call_openai_format(
            prompt, images,
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            base_url=OPENAI_BASE_URL,
        )

    def _call_claude(self, prompt, images):
        content = []
        for img_bytes, mime in images:
            b64 = _image_to_base64(img_bytes)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": b64,
                },
            })
        content.append({"type": "text", "text": prompt})

        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]

    def _parse_response(self, raw):
        result = {
            "market_phase": "unknown",
            "ema20_position": "unknown",
            "trend_direction": "unknown",
            "gap_exists": False,
            "gap_bars": 0,
            "push_count": 0,
            "opportunities": [],
            "warnings": [],
            "summary": "",
            "raw_response": raw,
        }

        json_str = raw.strip()

        # 去掉可能的markdown代码块包裹
        if json_str.startswith("```"):
            lines = json_str.split("\n")
            json_str = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            parsed = json.loads(json_str)
            for key in ["market_phase", "ema20_position", "trend_direction",
                        "gap_exists", "gap_bars", "push_count",
                        "opportunities", "warnings", "summary"]:
                if key in parsed:
                    result[key] = parsed[key]
        except json.JSONDecodeError:
            result["summary"] = raw[:500]
            result["warnings"] = ["AI返回格式异常，以下为原始分析文本"]

        return result
