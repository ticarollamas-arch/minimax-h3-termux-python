#!/usr/bin/env python3
# MiniMax-H3 local API for Termux. Uses only Python standard library.
import os, sys, json, time, getpass, secrets, argparse, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONFIG = Path.home() / ".minimax_h3_config.json"
DEFAULT_BASE = "https://metaso.cn/api/minimax"

def load_config():
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        CONFIG.chmod(0o600)
    except Exception:
        pass

def setup():
    cfg = load_config()
    print("\n=== Configuração MiniMax-H3 / Metaso ===")
    print("Base URL padrão: " + DEFAULT_BASE)
    base = input("Base URL [Enter para manter]: ").strip() or cfg.get("base_url") or DEFAULT_BASE
    token = getpass.getpass("Cole sua chave Metaso (começa geralmente com mk-): ").strip()
    if not token:
        token = cfg.get("metaso_api_key", "")
    if not token:
        print("ERRO: a chave Metaso é necessária. O script não consegue criar uma chave do fornecedor.")
        print("Obtenha-a em https://metaso.cn/minimax-h3 depois de entrar na conta.")
        sys.exit(2)
    local_key = cfg.get("local_api_key") or ("local-" + secrets.token_urlsafe(32))
    save_config({"base_url": base.rstrip("/"), "metaso_api_key": token, "local_api_key": local_key})
    print("\nConfiguração salva em", CONFIG)
    print("Chave de acesso da API local (guarde-a):", local_key)
    print("Não envie nem publique essa chave ou a chave Metaso.")

def cfg_required():
    cfg = load_config()
    for k in ("base_url", "metaso_api_key", "local_api_key"):
        if not cfg.get(k):
            print("Configuração incompleta. Execute: python minimax_h3.py setup")
            sys.exit(2)
    return cfg

def request_json(url, method="GET", payload=None, token=None, timeout=120):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try: body = json.loads(raw)
        except Exception: body = {"message": raw[:1500]}
        return e.code, body
    except Exception as e:
        return 0, {"message": str(e)}

def create_video(cfg, body):
    prompt = str(body.get("prompt", "")).strip()
    content = body.get("content")
    if not content:
        if not prompt:
            return 400, {"error": "Informe 'prompt'."}
        content = [{"type": "text", "text": prompt}]
    duration = int(body.get("duration", 5))
    resolution = str(body.get("resolution", "768P"))
    ratio = str(body.get("ratio", "9:16"))
    if duration < 4 or duration > 15:
        return 400, {"error": "duration deve ser de 4 a 15 segundos."}
    if resolution not in ("768P", "2K"):
        return 400, {"error": "resolution deve ser 768P ou 2K."}
    if ratio not in ("adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16"):
        return 400, {"error": "ratio inválido."}
    payload = {"model": "MiniMax-H3", "content": content,
               "resolution": resolution, "duration": duration, "ratio": ratio}
    for key in ("callback_url", "aigc_watermark", "context_ir_enabled", "billing_policy"):
        if key in body: payload[key] = body[key]
    status, data = request_json(cfg["base_url"] + "/v2/video_generation",
                                "POST", payload, cfg["metaso_api_key"])
    if status not in (200, 201, 202):
        return (status or 502), {"error": "Falha na API Metaso", "details": data}
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    task_id = data.get("task_id") or task.get("id") or task.get("task_id")
    if not task_id:
        return 502, {"error": "A resposta não trouxe task_id", "details": data}
    return 202, {"task_id": str(task_id), "status": "queued", "provider_response": data}

def query_video(cfg, task_id):
    url = cfg["base_url"] + "/v2/query/video_generation/" + urllib.parse.quote(str(task_id), safe="")
    status, data = request_json(url, "GET", token=cfg["metaso_api_key"], timeout=60)
    if status != 200:
        return (status or 502), {"error": "Falha ao consultar tarefa", "details": data}
    task = data.get("task") if isinstance(data.get("task"), dict) else data
    state = str(task.get("status", "unknown")).lower()
    result = {"task_id": str(task.get("id") or task.get("task_id") or task_id), "status": state}
    if state in ("succeeded", "success", "completed"):
        result["video_url"] = (task.get("content") or {}).get("url")
    if state in ("failed", "failure", "cancelled"):
        result["error"] = (task.get("error") or {}).get("message", "Geração falhou")
    result["provider_response"] = data
    return 200, result

class Handler(BaseHTTPRequestHandler):
    def _send(self, status, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self, cfg):
        auth = self.headers.get("Authorization", "")
        return auth == "Bearer " + cfg["local_api_key"]

    def do_GET(self):
        cfg = cfg_required()
        if self.path == "/health":
            return self._send(200, {"ok": True, "service": "MiniMax-H3 local API"})
        if not self._authorized(cfg):
            return self._send(401, {"error": "Unauthorized"})
        if self.path.startswith("/v1/videos/"):
            task_id = self.path.split("/v1/videos/", 1)[1].split("?", 1)[0]
            status, result = query_video(cfg, task_id)
            return self._send(status, result)
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        cfg = cfg_required()
        if not self._authorized(cfg):
            return self._send(401, {"error": "Unauthorized"})
        if self.path != "/v1/videos":
            return self._send(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 10_000_000:
                return self._send(413, {"error": "Payload muito grande"})
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            status, result = create_video(cfg, body)
            return self._send(status, result)
        except Exception as e:
            return self._send(400, {"error": str(e)})

    def log_message(self, fmt, *args):
        print("[API]", fmt % args)

def serve(host="127.0.0.1", port=8000):
    cfg = cfg_required()
    print(f"\nAPI local rodando em http://{host}:{port}")
    print("Teste: http://127.0.0.1:8000/health")
    print("Use Authorization: Bearer <sua_chave_local> nos endpoints /v1.")
    print("Pare com CTRL+C.")
    ThreadingHTTPServer((host, port), Handler).serve_forever()

def generate_cli(prompt, duration, resolution, ratio):
    cfg = cfg_required()
    status, result = create_video(cfg, {"prompt": prompt, "duration": duration,
                                         "resolution": resolution, "ratio": ratio})
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if status not in (200, 201, 202):
        sys.exit(1)
    task_id = result["task_id"]
    print("\nAguardando geração do vídeo...")
    for _ in range(90):
        time.sleep(10)
        st, task = query_video(cfg, task_id)
        print("Status:", task.get("status"))
        if st == 200 and task.get("status") in ("succeeded", "success", "completed"):
            url = task.get("video_url")
            if not url:
                print("Tarefa concluída, mas a resposta não trouxe video_url.")
                print(json.dumps(task, indent=2, ensure_ascii=False))
                return
            out = Path("minimax_h3_video.mp4")
            req = urllib.request.Request(url, headers={"User-Agent": "MiniMax-H3-Termux/1.0"})
            with urllib.request.urlopen(req, timeout=180) as resp, out.open("wb") as f:
                f.write(resp.read())
            print("\nVídeo salvo em:", out.resolve())
            return
        if task.get("status") in ("failed", "failure", "cancelled"):
            print(json.dumps(task, indent=2, ensure_ascii=False))
            sys.exit(1)
    print("Ainda processando. Consulte depois com GET /v1/videos/" + task_id)

def main():
    p = argparse.ArgumentParser(description="API local MiniMax-H3 para Termux")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="configurar chave Metaso e chave local")
    s = sub.add_parser("serve", help="iniciar API HTTP local")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    g = sub.add_parser("generate", help="gerar MP4 direto pelo Termux")
    g.add_argument("prompt")
    g.add_argument("--duration", type=int, default=5)
    g.add_argument("--resolution", choices=["768P", "2K"], default="768P")
    g.add_argument("--ratio", default="9:16")
    args = p.parse_args()
    if args.cmd == "setup": setup()
    elif args.cmd == "serve": serve(args.host, args.port)
    elif args.cmd == "generate": generate_cli(args.prompt, args.duration, args.resolution, args.ratio)

if __name__ == "__main__":
    import urllib.parse
    main()
