"""OpenAI → Claude Code 代理服务"""
import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from config import BASE_URL, API_KEY, MODEL_NAME, DEFAULT_MAX_TOKENS, PORT, PROXY_API_KEY
from claudecode_headers import build_headers
from converter import convert_request, convert_response
from stream_converter import StreamConverter

app = FastAPI(title="LLM API → Claude Code Proxy")

# 复用 HTTP 客户端
client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0))


def _check_auth(request: Request):
    """校验客户端 API Key（如果配置了 PROXY_API_KEY）"""
    if not PROXY_API_KEY:
        return
    auth = request.headers.get("Authorization", "")
    key = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
    if key != PROXY_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """核心端点：接收 OpenAI 格式请求，转发为 Claude Code 格式"""
    _check_auth(request)

    body = await request.json()
    is_stream = body.get("stream", False)

    # 转换请求
    anthropic_body = convert_request(body)

    # 构建发送到 Anthropic 的请求头
    headers = build_headers()
    if is_stream:
        headers["Accept"] = "text/event-stream"

    url = f"{BASE_URL}/v1/messages"

    if is_stream:
        return await _handle_stream(url, headers, anthropic_body)
    else:
        return await _handle_non_stream(url, headers, anthropic_body)


async def _handle_non_stream(url: str, headers: dict, body: dict) -> JSONResponse:
    """处理非流式请求"""
    try:
        resp = await client.post(url, headers=headers, json=body)
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接上游: {e}")

    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:
            err = {"error": {"message": resp.text}}
        raise HTTPException(status_code=resp.status_code, detail=err)

    anthropic_resp = resp.json()
    openai_resp = convert_response(anthropic_resp, MODEL_NAME)
    return JSONResponse(content=openai_resp)


async def _handle_stream(url: str, headers: dict, body: dict) -> StreamingResponse:
    """处理流式请求"""
    async def stream_generator():
        converter = StreamConverter(MODEL_NAME)
        async with client.stream("POST", url, headers=headers, json=body) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                error_msg = error_body.decode()
                err_chunk = {
                    "error": {
                        "message": f"上游返回 {resp.status_code}: {error_msg}",
                        "type": "upstream_error",
                    }
                }
                yield f"data: {json.dumps(err_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            async for line in resp.aiter_lines():
                for out_line in converter.process_line(line):
                    yield out_line

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/v1/models")
async def list_models(request: Request):
    """返回可用模型列表（OpenAI 兼容格式）"""
    _check_auth(request)
    return {
        "object": "list",
        "data": [{
            "id": MODEL_NAME,
            "object": "model",
            "created": 1700000000,
            "owned_by": "anthropic",
        }],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "upstream": BASE_URL, "model": MODEL_NAME}


if __name__ == "__main__":
    import uvicorn
    if not API_KEY:
        print("警告: API_KEY 未设置，请在 .env 中配置")
    print(f"代理启动 → 上游: {BASE_URL}, 模型: {MODEL_NAME}, 端口: {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
