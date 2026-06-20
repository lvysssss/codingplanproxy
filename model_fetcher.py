"""从 Anthropic Models API 动态获取可用模型列表"""
import logging
import httpx
from config import BASE_URL, API_KEY

logger = logging.getLogger(__name__)

# Models API 使用的 anthropic-version（与 Messages API 不同）
MODELS_API_VERSION = "2023-06-01"


async def fetch_anthropic_models() -> list[str]:
    """从上游 Anthropic 兼容 API 获取所有可用模型 ID 列表。
    
    调用 GET /v1/models，处理游标分页（has_more），失败时返回空列表。
    """
    if not API_KEY:
        logger.warning("API_KEY 未设置，跳过远端模型获取")
        return []

    headers = {
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {API_KEY}",
        "anthropic-version": MODELS_API_VERSION,
    }
    url = f"{BASE_URL}/v1/models?limit=1000"

    all_models: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            while True:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    logger.warning(
                        "获取远端模型列表失败: HTTP %s, body=%s",
                        resp.status_code,
                        resp.text[:500],
                    )
                    return []

                data = resp.json()
                models_data = data.get("data", [])
                for m in models_data:
                    model_id = m.get("id", "")
                    if model_id:
                        all_models.append(model_id)

                # 游标分页：has_more 为 true 时继续
                if data.get("has_more") and data.get("last_id"):
                    url = f"{BASE_URL}/v1/models?limit=1000&after_id={data['last_id']}"
                else:
                    break

        logger.info("从远端获取到 %d 个模型", len(all_models))
        return all_models

    except httpx.ConnectError as e:
        logger.warning("连接远端模型 API 失败: %s", e)
        return []
    except Exception as e:
        logger.warning("获取远端模型列表异常: %s", e)
        return []
