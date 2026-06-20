"""模型注册中心：合并本地配置与远端获取的模型列表，带 TTL 缓存"""
import asyncio
import logging
import time
from config import AVAILABLE_MODELS
from model_fetcher import fetch_anthropic_models

logger = logging.getLogger(__name__)

# 缓存 TTL（秒）
CACHE_TTL = 30 * 60  # 30 分钟


class ModelRegistry:
    """单例模型注册中心。
    
    合并本地 AVAILABLE_MODELS 与远端 Anthropic Models API 返回的模型列表，
    去重后缓存，过期自动刷新。
    """

    def __init__(self):
        self._models: list[str] = []
        self._remote_models: list[str] = []
        self._last_fetch: float = 0
        self._lock = asyncio.Lock()

    async def get_models(self) -> list[str]:
        """获取当前可用模型列表（合并本地 + 远端，去重）。
        
        如果缓存过期，自动触发远端刷新。
        """
        if self._is_expired():
            await self.refresh()
        return list(self._models)

    async def refresh(self) -> list[str]:
        """强制刷新：从远端拉取模型并与本地合并。"""
        async with self._lock:
            # 双重检查：可能另一个协程已经刷新过
            if not self._is_expired() and self._models:
                return list(self._models)

            self._remote_models = await fetch_anthropic_models()
            self._last_fetch = time.time()
            self._models = self._merge()
            logger.info(
                "模型列表已刷新: 本地 %d + 远端 %d → 合并 %d",
                len(AVAILABLE_MODELS),
                len(self._remote_models),
                len(self._models),
            )
            return list(self._models)

    async def startup_refresh(self) -> None:
        """启动时初始化：拉取远端模型（失败不阻塞）。"""
        try:
            await self.refresh()
        except Exception as e:
            logger.warning("启动时模型拉取失败，使用本地配置: %s", e)
            self._models = list(AVAILABLE_MODELS)

    def _merge(self) -> list[str]:
        """合并本地 + 远端，保持顺序：本地在前，远端在后，去重。"""
        seen = set()
        merged = []
        for m in AVAILABLE_MODELS:
            if m not in seen:
                merged.append(m)
                seen.add(m)
        for m in self._remote_models:
            if m not in seen:
                merged.append(m)
                seen.add(m)
        return merged

    def _is_expired(self) -> bool:
        return (time.time() - self._last_fetch) > CACHE_TTL

    @property
    def remote_count(self) -> int:
        return len(self._remote_models)

    @property
    def local_count(self) -> int:
        return len(AVAILABLE_MODELS)


# 全局单例
registry = ModelRegistry()
