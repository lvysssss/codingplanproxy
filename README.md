# CodingPlanProxy

OpenAI-to-Anthropic API 代理服务。将 OpenAI `/v1/chat/completions` 格式请求转换为 Anthropic `/v1/messages` 格式并转发，响应再转回 OpenAI 格式返回客户端。请求头伪装为 Claude Code CLI 客户端，使任何支持 OpenAI API 的客户端都能直接访问 Anthropic Claude 模型。

## 功能特性

- **OpenAI 格式兼容** — 完整实现 `/v1/chat/completions` 和 `/v1/models` 端点，兼容所有使用 OpenAI SDK 的客户端
- **双向格式转换** — 请求/响应自动转换，包括 tool calls、tool results、图片输入等复杂场景
- **流式输出** — 支持 SSE 流式响应，逐 token 实时返回
- **Claude Code 伪装** — 请求头模拟 Claude Code CLI，启用 prompt caching 和 computer-use 等 beta 特性
- **动态模型选择** — 请求中指定 `model` 字段时使用请求值，否则使用配置的默认模型
- **可选鉴权** — 支持为代理设置 API Key，防止未授权访问
- **System Prompt 注入** — 可选在无 system 消息时自动注入默认 system prompt

## 目标用户

- 需要通过 OpenAI 兼容客户端（如 ChatGPT 前端、OpenAI SDK）访问 Claude 模型的开发者
- 希望利用 Claude Code 特有特性（prompt caching、computer-use）的用户
- 需要统一多模型 API 格式的团队

## 安装

### 前置要求

- Python 3.10+
- Anthropic API Key（[获取地址](https://console.anthropic.com/)）

### 安装步骤

1. 克隆仓库：

```bash
git clone https://github.com/lvysssss/codingplanproxy.git
cd codingplanproxy
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

依赖列表：
| 包 | 最低版本 | 用途 |
|---|---|---|
| fastapi | 0.110.0 | Web 框架 |
| uvicorn | 0.29.0 | ASGI 服务器 |
| httpx | 0.27.0 | 异步 HTTP 客户端 |
| python-dotenv | 1.0.0 | .env 文件加载 |

3. 配置环境变量：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 Anthropic API Key（必填），其余按需配置。

4. 启动服务：

```bash
python main.py
```

Windows 用户可双击 `startcodingplanproxy.bat` 一键启动。

启动成功后会看到：

```
代理启动 → 上游: https://api.anthropic.com, 模型: claude-sonnet-4-20250514, 端口: 8000
```

## 配置

所有配置通过项目根目录的 `.env` 文件管理，参考 `.env.example`：

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `BASE_URL` | 否 | `https://api.anthropic.com` | Anthropic API 上游地址，可改为中转地址 |
| `API_KEY` | **是** | — | Anthropic API Key，以 `sk-ant-` 开头 |
| `MODEL_NAME` | 否 | `claude-sonnet-4-20250514` | 默认使用的模型，请求中未指定 model 时生效 |
| `DEFAULT_MAX_TOKENS` | 否 | `16384` | 默认最大输出 token 数 |
| `SYSTEM_PROMPT` | 否 | （空） | 注入的默认 system prompt，仅在请求无 system 消息时生效 |
| `PORT` | 否 | `8000` | 代理服务监听端口 |
| `PROXY_API_KEY` | 否 | （空） | 客户端调用代理时需提供的 API Key，留空则不校验 |

### 配置示例

最简配置（只需 API Key）：

```env
API_KEY=sk-ant-api03-your-key-here
```

完整配置：

```env
BASE_URL=https://api.anthropic.com
API_KEY=sk-ant-api03-your-key-here
MODEL_NAME=claude-sonnet-4-20250514
DEFAULT_MAX_TOKENS=16384
SYSTEM_PROMPT=You are a helpful assistant.
PORT=8000
PROXY_API_KEY=my-proxy-secret
```

## 使用

代理启动后，所有端点兼容 OpenAI API 格式。将你的 OpenAI 客户端 base_url 指向代理地址即可。
baseurl: http://localhost:8000/v1
### 端点列表

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/chat/completions` | 核心端点，聊天补全 |
| GET | `/v1/models` | 返回可用模型列表 |
| GET | `/health` | 健康检查 |

### 基础对话

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [
      {"role": "user", "content": "Hello, who are you?"}
    ]
  }'
```

### 流式输出

添加 `"stream": true` 即可启用 SSE 流式响应：

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [
      {"role": "user", "content": "Write a poem about coding"}
    ],
    "stream": true
  }'
```

### 带 System Prompt

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [
      {"role": "system", "content": "You are a Python expert."},
      {"role": "user", "content": "How to read a file in Python?"}
    ]
  }'
```

### Tool Calling

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [
      {"role": "user", "content": "What is the weather in Beijing?"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "Get current weather for a city",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"]
          }
        }
      }
    ],
    "tool_choice": "auto"
  }'
```

返回 tool_calls 后，提交 tool 结果继续对话：

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [
      {"role": "user", "content": "What is the weather in Beijing?"},
      {"role": "assistant", "content": null, "tool_calls": [
        {"id": "call_abc123", "type": "function", "function": {"name": "get_weather", "arguments": "{\"city\": \"Beijing\"}"}}
      ]},
      {"role": "tool", "tool_call_id": "call_abc123", "content": "25°C, sunny"}
    ]
  }'
```

### 图片输入（Base64）

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [
      {"role": "user", "content": [
        {"type": "text", "text": "What is in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}}
      ]}
    ]
  }'
```

### 使用代理鉴权

配置 `PROXY_API_KEY` 后，请求需携带 Authorization 头：

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-proxy-secret" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }'
```

### Python SDK 接入

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="any-string"  # 未配置 PROXY_API_KEY 时可填任意值
)

response = client.chat.completions.create(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### Node.js 接入

```javascript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "any-string",
});

const stream = await client.chat.completions.create({
  model: "claude-sonnet-4-20250514",
  messages: [{ role: "user", content: "Hello!" }],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
}
```

### 动态模型选择

请求中指定 `model` 字段可覆盖默认模型，无需修改配置：

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-opus-4-20250514",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }'
```

### 支持的请求参数

| OpenAI 参数 | Anthropic 映射 | 说明 |
|---|---|---|
| `model` | `model` | 模型名称，支持动态选择 |
| `messages` | `messages` + `system` | system 消息提取为顶层字段 |
| `max_tokens` / `max_completion_tokens` | `max_tokens` | 最大输出 token |
| `temperature` | `temperature` | 采样温度 |
| `top_p` | `top_p` | 核采样 |
| `stream` | `stream` | 是否流式输出 |
| `stop` | `stop_sequences` | 停止序列，字符串或数组 |
| `tools` | `tools` | 工具定义，function → input_schema |
| `tool_choice` | `tool_choice` | auto/required/none/function |

## 故障排除

### 启动时提示 "API_KEY 未设置"

确认 `.env` 文件存在于项目根目录，且 `API_KEY` 已填入有效值：

```env
API_KEY=sk-ant-api03-xxxxxxxxxxxx
```

### 请求返回 401 Unauthorized

- 如果配置了 `PROXY_API_KEY`，请求需携带 `Authorization: Bearer <your-proxy-key>` 头
- 如果未配置 `PROXY_API_KEY` 仍返回 401，确认请求头格式正确

### 请求返回 502 Bad Gateway

- 检查 `BASE_URL` 是否正确，网络是否能访问 Anthropic API
- 如果在国内，可能需要设置 HTTP 代理或使用中转地址：

```env
BASE_URL=https://your-proxy-domain.com
```

### 流式响应中断 / 无 [DONE] 标记

上游连接断开时，流式响应可能缺少 `[DONE]` 标记。检查：
- 网络稳定性
- 上游 API 是否超时（代理默认 300 秒超时）
- 是否触发了 Anthropic API 的速率限制

### Tool Calling 不生效

- 确认 `tools` 参数格式符合 OpenAI 规范（`type: "function"` + `function` 对象）
- `tool_choice` 值 `none` 在 Anthropic 中无直接对应，代理映射为 `auto`
- 返回的 tool result 消息需使用 `role: "tool"` 并携带 `tool_call_id`

### 模型名称不生效

请求中的 `model` 字段优先级高于 `.env` 中的 `MODEL_NAME`。如果未指定 model，才会使用默认值。

### 请求头版本过旧

`claudecode_headers.py` 中硬编码了 Claude Code 的请求头版本。如果 Anthropic 更新了 API，可能需要手动更新以下常量：

```python
CLAUDE_CODE_USER_AGENT = "claude-code/x.x.xxx (node/xx.x.x; darwin; amd64)"
ANTHROPIC_VERSION = "2026-04-14"
ANTHROPIC_BETA = "prompt-caching-2026-04-14,computer-use-2026-04-14"
```

## 贡献指南

欢迎贡献！请遵循以下流程：

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交改动：`git commit -m "feat: description of your change"`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

提交信息请使用 Conventional Commits 格式：

- `feat:` 新功能
- `fix:` 修复
- `refactor:` 重构
- `docs:` 文档
- `chore:` 杂项

## 许可证

MIT
