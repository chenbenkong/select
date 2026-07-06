"""
抉择·庭审记录 — 后端服务
- 提供静态文件服务（index.html 等）
- 代理 /api/chat 到 agnes API，转发流式 SSE
- 密钥通过环境变量 AGNES_API_KEY 注入，不进代码

本地：   python server.py
Render： 自动读取 render.yaml 启动
"""
import http.server
import socketserver
import urllib.request
import urllib.error
import json
import os
import sys

API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
API_KEY = os.environ.get("AGNES_API_KEY", "")
# HF Spaces 会自动注入 PORT=7860（来自 README.md 的 app_port）
PORT = int(os.environ.get("PORT") or 7860)
HOST = os.environ.get("HOST", "0.0.0.0")
ROOT = os.path.dirname(os.path.abspath(__file__))

MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.svg':  'image/svg+xml',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.ico':  'image/x-icon',
    '.json': 'application/json; charset=utf-8',
}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        # quieter logging
        sys.stderr.write("[%s] %s\n" % (self.command, self.path))

    # ---------- API proxy (no static files — front-end is hosted on Cloudflare Pages) ----------
    def do_GET(self):
        # HF 端只作为后端代理，不服务任何静态文件
        self.send_error(404)
        return

    # ---------- API proxy ----------
    def do_POST(self):
        if self.path != '/api/chat':
            self.send_error(404)
            return
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except Exception:
            self.send_error(400, 'invalid json')
            return

        stream = bool(req.get('stream', False))
        payload = json.dumps(req).encode('utf-8')
        headers = {
            'Authorization': 'Bearer ' + API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream' if stream else 'application/json',
        }
        request = urllib.request.Request(API_URL, data=payload, headers=headers, method='POST')

        try:
            resp = urllib.request.urlopen(request, timeout=120)
        except urllib.error.HTTPError as e:
            err_body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(err_body)
            return
        except Exception as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
            return

        if stream:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            data = resp.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    if not API_KEY:
        print("⚠  警告：AGNES_API_KEY 环境变量未设置，/api/chat 将无法工作。", flush=True)
    srv = Server((HOST, PORT), Handler)
    print(f"抉择·庭审记录 服务已启动", flush=True)
    print(f"  监听地址: http://{HOST}:{PORT}/", flush=True)
    print(f"  代理端点: http://{HOST}:{PORT}/api/chat  →  {API_URL}", flush=True)
    print(f"  按 Ctrl+C 停止", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止", flush=True)
        srv.shutdown()
