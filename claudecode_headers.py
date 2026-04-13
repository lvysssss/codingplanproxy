"""生成 Claude Code 伪装请求头"""
from config import API_KEY

CLAUDE_CODE_USER_AGENT = "claude-code/0.2.15 (node/20.10.0; darwin; arm64)"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BETA = "prompt-caching-2024-07-31,computer-use-2024-10-22"


def build_headers(extra_headers: dict | None = None) -> dict:
    """构建发送到 Anthropic API 的请求头，伪装为 Claude Code 客户端"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": ANTHROPIC_BETA,
        "User-Agent": CLAUDE_CODE_USER_AGENT,
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers
