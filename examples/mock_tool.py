"""极简 Echo 工具服务（示例用，零第三方依赖）。

作用：演示"工具节点"如何对接工作站——
  工具节点注册 skill 时把 endpoint_url 指向本服务；
  Agent 调 skill → manager 审批放行 → 工作站转发到本服务 → 结果回写。

用法：python mock_tool.py   # 监听 127.0.0.1:9001
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        resp = {
            "ok": True,
            "echo": data.get("params", {}),
            "skill_id": data.get("skill_id"),
        }
        payload = json.dumps(resp, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("[mock_tool] listening on http://127.0.0.1:9001")
    HTTPServer(("127.0.0.1", 9001), Handler).serve_forever()
