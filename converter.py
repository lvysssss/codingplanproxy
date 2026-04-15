"""OpenAI Chat Completions ↔ Anthropic Messages 格式转换"""
import json
import time
import uuid
from config import DEFAULT_MAX_TOKENS, SYSTEM_PROMPT


# ── 请求转换: OpenAI → Anthropic ──────────────────────────────────

def convert_request(body: dict, default_model: str) -> dict:
    """将 OpenAI /v1/chat/completions 请求体转为 Anthropic /v1/messages 请求体"""
    messages = body.get("messages", [])
    anthropic_messages = []
    system_text = ""

    # 1. 提取 system 消息，合并为顶层 system
    for msg in messages:
        if msg["role"] == "system":
            system_text += (msg.get("content") or "") + "\n"
    system_text = system_text.strip()

    # 如果没有 system 消息且配置了默认 SYSTEM_PROMPT，注入
    if not system_text and SYSTEM_PROMPT:
        system_text = SYSTEM_PROMPT

    # 2. 转换非 system 消息
    non_system = [m for m in messages if m["role"] != "system"]
    anthropic_messages = _convert_messages(non_system)

    # 3. 组装请求体
    result = {
        "model": body.get("model") or default_model,
        "max_tokens": body.get("max_tokens") or body.get("max_completion_tokens") or DEFAULT_MAX_TOKENS,
        "messages": anthropic_messages,
    }

    if system_text:
        result["system"] = system_text

    # stream
    if body.get("stream"):
        result["stream"] = True

    # temperature / top_p
    if "temperature" in body:
        result["temperature"] = body["temperature"]
    if "top_p" in body:
        result["top_p"] = body["top_p"]

    # stop_sequences
    if body.get("stop"):
        stops = body["stop"]
        if isinstance(stops, str):
            stops = [stops]
        result["stop_sequences"] = stops

    # tools
    if body.get("tools"):
        result["tools"] = _convert_tools(body["tools"])

    # tool_choice
    if "tool_choice" in body and body.get("tools"):
        result["tool_choice"] = _convert_tool_choice(body["tool_choice"])

    return result


def _convert_messages(messages: list) -> list:
    """转换消息列表，处理连续性和格式差异"""
    result = []
    # 将连续相同 role 的消息合并，确保 user/assistant 交替
    merged = _merge_consecutive_roles(messages)

    for msg in merged:
        role = msg["role"]
        content = msg.get("content")

        if role == "user":
            result.append({"role": "user", "content": _convert_user_content(content)})
        elif role == "assistant":
            result.append(_convert_assistant_msg(msg))
        elif role == "tool":
            # tool 消息转为 user + tool_result 内容块
            # 需要和前一条合并到 user role
            tool_result_block = {
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": msg.get("content") or "",
            }
            if result and result[-1]["role"] == "user":
                # 追加到已有 user 消息
                existing = result[-1]["content"]
                if isinstance(existing, list):
                    existing.append(tool_result_block)
                else:
                    result[-1]["content"] = [
                        {"type": "text", "text": existing},
                        tool_result_block,
                    ]
            else:
                result.append({"role": "user", "content": [tool_result_block]})

    return result


def _merge_consecutive_roles(messages: list) -> list:
    """合并连续相同 role 的消息为一条，处理 tool 角色的连续性"""
    if not messages:
        return []

    merged = []
    for msg in messages:
        if not merged:
            merged.append(dict(msg))
            continue

        last = merged[-1]
        # assistant + 连续 tool → 合并 tool 到后续
        if msg["role"] == "tool" and last["role"] in ("assistant", "tool"):
            merged.append(dict(msg))
            continue
        # 连续 user → 合并 content
        if msg["role"] == "user" and last["role"] == "user":
            last_content = last.get("content") or ""
            cur_content = msg.get("content") or ""
            if isinstance(last_content, str) and isinstance(cur_content, str):
                last["content"] = last_content + "\n" + cur_content
            else:
                last["content"] = _merge_content_blocks(last_content, cur_content)
            continue
        # 连续 assistant → 合并
        if msg["role"] == "assistant" and last["role"] == "assistant":
            # 如果前一条或当前有 tool_calls，不合并，保持独立
            if msg.get("tool_calls") or last.get("tool_calls"):
                merged.append(dict(msg))
                continue
            last_content = last.get("content") or ""
            cur_content = msg.get("content") or ""
            last["content"] = (last_content + "\n" + cur_content) if last_content and cur_content else (last_content or cur_content)
            continue

        merged.append(dict(msg))

    return merged


def _merge_content_blocks(a, b):
    """合并两个可能是字符串或列表的 content"""
    a_list = a if isinstance(a, list) else [{"type": "text", "text": str(a)}]
    b_list = b if isinstance(b, list) else [{"type": "text", "text": str(b)}]
    return a_list + b_list


def _convert_user_content(content) -> str | list:
    """转换 user 消息的 content"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # OpenAI 格式的 content 数组，可能含 image_url 等
        blocks = []
        for item in content:
            if item.get("type") == "text":
                blocks.append({"type": "text", "text": item["text"]})
            elif item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    # data:image/jpeg;base64,xxx
                    parts = url.split(",", 1)
                    meta = parts[0]  # data:image/jpeg;base64
                    data = parts[1] if len(parts) > 1 else ""
                    media_type = meta.split(";")[0].split(":")[1] if ":" in meta else "image/jpeg"
                    blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    })
            else:
                blocks.append(item)
        return blocks
    return str(content) if content else ""


def _convert_assistant_msg(msg: dict) -> dict:
    """转换 assistant 消息，处理 tool_calls"""
    content = msg.get("content") or ""
    tool_calls = msg.get("tool_calls", [])

    if not tool_calls:
        return {"role": "assistant", "content": content}

    # assistant 消息含 tool_calls → content 数组
    blocks = []
    if content:
        blocks.append({"type": "text", "text": content})
    for tc in tool_calls:
        func = tc.get("function", {})
        args = func.get("arguments", "{}")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        blocks.append({
            "type": "tool_use",
            "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
            "name": func.get("name", ""),
            "input": args,
        })
    return {"role": "assistant", "content": blocks}


def _convert_tools(tools: list) -> list:
    """转换工具定义: OpenAI function → Anthropic input_schema"""
    result = []
    for t in tools:
        if t.get("type") == "function":
            func = t.get("function", {})
            tool = {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            }
        else:
            tool = t
        result.append(tool)
    return result


def _convert_tool_choice(tc) -> dict:
    """转换 tool_choice"""
    if isinstance(tc, str):
        if tc == "auto":
            return {"type": "auto"}
        if tc == "required":
            return {"type": "any"}
        if tc == "none":
            return {"type": "auto"}  # Anthropic 无 none，用 auto 代替
    if isinstance(tc, dict):
        if tc.get("type") == "function":
            return {"type": "tool", "name": tc["function"]["name"]}
    return {"type": "auto"}


# ── 响应转换: Anthropic → OpenAI ──────────────────────────────────

def convert_response(resp: dict, model: str) -> dict:
    """将 Anthropic 非流式响应转为 OpenAI 格式"""
    content_blocks = resp.get("content", [])
    text_parts = []
    tool_calls = []

    for block in content_blocks:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                },
            })

    message = {"role": "assistant", "content": "".join(text_parts)}
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason = _map_stop_reason(resp.get("stop_reason"))

    usage = resp.get("usage", {})
    return {
        "id": f"chatcmpl-{resp.get('id', uuid.uuid4().hex[:29])}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": finish_reason,
        }],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
    }


def _map_stop_reason(reason: str | None) -> str:
    """映射 Anthropic stop_reason → OpenAI finish_reason"""
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    return mapping.get(reason, "stop")
