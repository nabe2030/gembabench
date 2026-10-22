#!/usr/bin/env python3
"""Scripted OpenAI-compatible server to verify the harness behaviour (no real model). Listens on 127.0.0.1 only.
Script for requests that carry tools: #1 background shell call (sleep N) -> #2 plain text 'waiting' (the point where headless `run` ends)
-> (only if OpenCode resumed after the completion notice) #3 foreground shell `cat` of the result file -> #4 final text 'FINISHED-AFTER-RESUME'.
Requests without tools (title/small model) get plain text. Every request is saved raw. usage: scripted_server.py <port> <outdir> <sleep_s> [nobg]"""
import json, sys, os, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
port, outdir, SLEEP = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]); NOBG = len(sys.argv) > 4
os.makedirs(outdir, exist_ok=True); lock = threading.Lock(); st = {"n": 0, "main": 0}
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_GET(self):
        b = json.dumps({"object": "list", "data": [{"id": "scripted", "object": "model"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0)); req = json.loads(raw or b"{}")
        with lock:
            st["n"] += 1; n = st["n"]; has_tools = bool(req.get("tools"))
            if has_tools: st["main"] += 1
            m = st["main"]
        open(os.path.join(outdir, "req_%02d_main%d.json" % (n, m if has_tools else 0)), "wb").write(raw)
        open(os.path.join(outdir, "reqlog.txt"), "a").write("%s req#%d tools=%s main#%d nmsg=%d\n" % (time.strftime("%H:%M:%S"), n, has_tools, m, len(req.get("messages", []))))
        now = int(time.time()); cid = "chatcmpl-s%d" % n
        def chunk(delta, fin=None): return {"id": cid, "object": "chat.completion.chunk", "created": now, "model": "scripted", "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
        call = None; text = "OK"
        if has_tools:
            if m == 1:
                a = {"command": os.environ.get("SVCMD") or "sleep %d; echo BGDONE > /tmp/svtest/bg.txt" % SLEEP, "background": not NOBG, "description": "bg job"}
                if NOBG: a.pop("background")
                call = ("call_bg1", "shell", a); text = None
            elif m == 2: text = "The background job is running; I will wait for it to finish."
            elif m == 3: call = ("call_cat", "shell", {"command": "cat /tmp/svtest/bg.txt"}); text = None
            else: text = "FINISHED-AFTER-RESUME"
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Connection", "close"); self.end_headers()
        def ev(d): self.wfile.write(("data: " + (d if isinstance(d, str) else json.dumps(d)) + "\n\n").encode()); self.wfile.flush()
        ev(chunk({"role": "assistant", "content": ""}))
        if call:
            ev(chunk({"tool_calls": [{"index": 0, "id": call[0], "type": "function", "function": {"name": call[1], "arguments": json.dumps(call[2])}}]})); ev(chunk({}, "tool_calls"))
        else:
            ev(chunk({"content": text})); ev(chunk({}, "stop"))
        ev({"id": cid, "object": "chat.completion.chunk", "created": now, "model": "scripted", "choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}); ev("[DONE]")
ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
