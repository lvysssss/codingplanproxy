import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API 固定配置
BASE_URL = os.getenv("BASE_URL", "https://api.anthropic.com").rstrip("/")
API_KEY = os.getenv("API_KEY", "")

# 多模型支持：逗号分隔的可用模型列表（如 "claude-sonnet-4-20250514,claude-opus-4-20250514"）
# 请求中的 model 字段必须在白名单内，否则返回 400
# 如果未配置，默认只包含一个模型
_available_models = os.getenv("AVAILABLE_MODELS", "")
if _available_models:
    AVAILABLE_MODELS = [m.strip() for m in _available_models.split(",") if m.strip()]
else:
    AVAILABLE_MODELS = ["claude-sonnet-4-20250514"]

DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "16384"))

# 可选注入的 system prompt（留空则不注入）
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")

# 代理服务端口
PORT = int(os.getenv("PORT", "8000"))

# 认证：客户端调用代理时使用的 API Key（留空则不校验）
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "")
