"""
AI模型配置
优先读取 ai_config.json，其次读取环境变量
"""

import os
import json

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_FILE = os.path.join(_BASE_DIR, "ai_config.json")

# 从文件读取配置
_file_cfg = {}
if os.path.exists(_CONFIG_FILE):
    try:
        with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
            _file_cfg = json.load(f)
    except Exception:
        pass


def _cfg(key, default=""):
    """优先文件配置，其次环境变量"""
    val = _file_cfg.get(key, "")
    if val:
        return val
    return os.environ.get(key, default)


AI_PROVIDER = _cfg("AI_PROVIDER", "openai")

# OpenAI (同时兼容所有 OpenAI 协议的模型，包括各种 coding plan)
OPENAI_API_KEY = _cfg("OPENAI_API_KEY", "")
OPENAI_MODEL = _cfg("OPENAI_MODEL", "gpt-4o")
OPENAI_BASE_URL = _cfg("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Anthropic Claude
ANTHROPIC_API_KEY = _cfg("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = _cfg("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# 智谱 GLM
ZHIPU_API_KEY = _cfg("ZHIPU_API_KEY", "")
ZHIPU_MODEL = _cfg("ZHIPU_MODEL", "glm-4v-plus")

# 通义千问
DASHSCOPE_API_KEY = _cfg("DASHSCOPE_API_KEY", "")
QWEN_MODEL = _cfg("QWEN_MODEL", "qwen-vl-max")

# DeepSeek
DEEPSEEK_API_KEY = _cfg("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = _cfg("DEEPSEEK_MODEL", "deepseek-chat")

# 模型提供商映射
PROVIDERS = {
    "openai": {
        "name": "OpenAI (GPT-4o / GPT-4.1)",
        "env_key": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"],
    },
    "claude": {
        "name": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
    },
    "zhipu": {
        "name": "智谱 (GLM-4V)",
        "env_key": "ZHIPU_API_KEY",
        "models": ["glm-4v-plus", "glm-4v"],
    },
    "qwen": {
        "name": "通义千问 (Qwen-VL)",
        "env_key": "DASHSCOPE_API_KEY",
        "models": ["qwen-vl-max", "qwen-vl-plus"],
    },
    "deepseek": {
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "models": ["deepseek-chat"],
    },
}


def get_current_provider():
    return PROVIDERS.get(AI_PROVIDER, PROVIDERS["openai"])


def is_configured():
    p = get_current_provider()
    key = _cfg(p["env_key"], "")
    return bool(key)
