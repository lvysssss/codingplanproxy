import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API 固定配置
BASE_URL = os.getenv("BASE_URL", "https://api.anthropic.com").rstrip("/")
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-20250514")
DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "16384"))

# 可选注入的 system prompt（留空则不注入）
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")

# 代理服务端口
PORT = int(os.getenv("PORT", "8000"))

# 认证：客户端调用代理时使用的 API Key（留空则不校验）
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")
