"""Anthropic SSE 流式响应 → OpenAI SSE 流式响应 实时转换"""
import json
import time
import uuid
from config import MODEL_NAME


class StreamConverter:
    """有状态的 SSE 流转换器，逐行处理 Anthropic 事件，输出 OpenAI 格式"""

    def __init__(self, model: str = MODEL_NAME):
        self.model = model
        self.completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        self.created = int(time.time())
        self.current_tool_id = None
        self.current_tool_name = None
        self.current_tool_index = 0

    def process_line(self, raw_line: str) -> list[str]:
        """
        处理一行 Anthropic SSE 文本，返回零到多行 OpenAI SSE 输出。
        每行格式为 "data: {...}\\n\\n"。
        """
        line = raw_line.strip() if isinstance(raw_line, str) else raw_line.decode().strip()

        if not line:
            return []
        if line.startswith("event:"):
            return []
        if not line.startswith("data:"):
            return []

        data_str = line[len("data:"):].strip()
        if data_str == "[DONE]":
            return ["data: [DONE]\n\n"]

        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            return []

        event_type = event.get("type", "")
        handler = {
            "message_start": self._on_message_start,
            "content_block_start": self._on_content_block_start,
            "content_block_delta": self._on_content_block_delta,
            "content_block_stop": self._on_content_block_stop,
            "message_delta": self._on_message_delta,
            "message_stop": self._on_message_stop,
        }.get(event_type)

        if handler:
            return handler(event)
        return []

    # ── 事件处理器 ──

    def _on_message_start(self, event: dict) -> list[str]:
        chunk = self._build_chunk({"role": "assistant", "content": ""})
        return [self._fmt(chunk)]

    def _on_content_block_start(self, event: dict) -> list[str]:
        block = event.get("content_block", {})
        block_type = block.get("type", "")

        if block_type == "tool_use":
            self.current_tool_id = block.get("id", f"call_{uuid.uuid4().hex[:24]}")
            self.current_tool_name = block.get("name", "")
            delta = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "index": self.current_tool_index,
                    "id": self.current_tool_id,
                    "type": "function",
                    "function": {
                        "name": self.current_tool_name,
                        "arguments": "",
                    },
                }],
            }
            return [self._fmt(self._build_chunk(delta))]
        return []

    def _on_content_block_delta(self, event: dict) -> list[str]:
        delta = event.get("delta", {})
        delta_type = delta.get("type", "")

        if delta_type == "text_delta" or "text" in delta:
            text = delta.get("text", "")
            if text:
                return [self._fmt(self._build_chunk({"content": text}))]
            return []

        if delta_type == "input_json_delta" or "partial_json" in delta:
            partial = delta.get("partial_json", "")
            oai_delta = {
                "tool_calls": [{
                    "index": self.current_tool_index,
                    "function": {"arguments": partial},
                }],
            }
            return [self._fmt(self._build_chunk(oai_delta))]

        # thinking_delta 等跳过
        return []

    def _on_content_block_stop(self, event: dict) -> list[str]:
        # tool_use 块结束，递增 index 为下一个 tool 准备
        if self.current_tool_id is not None:
            self.current_tool_index += 1
            self.current_tool_id = None
            self.current_tool_name = None
        return []

    def _on_message_delta(self, event: dict) -> list[str]:
        delta_data = event.get("delta", {})
        stop_reason = delta_data.get("stop_reason")
        finish_reason = _map_stop_reason(stop_reason)
        chunk = self._build_chunk({"content": None}, finish_reason)
        return [self._fmt(chunk)]

    def _on_message_stop(self, event: dict) -> list[str]:
        return ["data: [DONE]\n\n"]

    # ── 辅助 ──

    def _build_chunk(self, delta: dict, finish_reason: str | None = None) -> dict:
        return {
            "id": self.completion_id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }],
        }

    @staticmethod
    def _fmt(chunk: dict) -> str:
        return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


def _map_stop_reason(reason: str | None) -> str:
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    return mapping.get(reason, "stop")
