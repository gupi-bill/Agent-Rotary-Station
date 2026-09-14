"""API 认证中间件：用 ARS_STATION_TOKEN 做 Bearer token 校验。

未配置（空）时放行所有请求（开发模式）。
已配置时，除 health / docs / swagger / webui 外的所有路由都需要 token。
"""
from __future__ import annotations

import os

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class AuthMiddleware(BaseHTTPMiddleware):
    """Bearer token 校验中间件。"""

    _SKIP_PREFIXES = ("/docs", "/openapi.json", "/redoc", "/webui", "/system/health")
    _TOKEN = os.getenv("ARS_STATION_TOKEN", "").strip()

    async def dispatch(self, request: Request, call_next):
        if not self._TOKEN:
            return await call_next(request)
        if any(request.url.path.startswith(p) for p in self._SKIP_PREFIXES):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            if token == self._TOKEN:
                response = await call_next(request)
                return response
        return Response(
            b'{"error":"unauthorized"}',
            status_code=401,
            media_type="application/json",
        )