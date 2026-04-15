"""生成 Claude Code 伪装请求头"""
from config import API_KEY

CLAUDE_CODE_USER_AGENT = "claude-code/2.1.107 (node/25.8.0; darwin; amd64)"
ANTHROPIC_VERSION = "2026-04-14"
ANTHROPIC_BETA = "prompt-caching-2026-04-14,computer-use-2026-04-14"


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
