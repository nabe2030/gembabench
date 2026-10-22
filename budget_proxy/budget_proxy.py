#!/usr/bin/env python3
"""budget_proxy.py -- thinking-budget proxy . OpenAI-compatible /v1/chat/completions in front of an engine that cannot cap the thinking itself (SGLang on Spark: reasoning_budget_tokens / thinking_budget are ignored).
For every request: the thinking budget = the request's `reasoning_budget_tokens` (default 8192); the output cap = max_tokens / max_completion_tokens (default 16384, thinking included).
The upstream is always called with stream=true. Thinking tokens (delta.reasoning_content chunks, ~1 token per chunk) are counted; when the count reaches the budget while the model is still thinking, the upstream stream is closed and generation is
CONTINUED with the thinking closed (`</think>` appended: see CONTINUE_MODE) so the model goes on with the answer / tool call. The client sees ONE continuous stream (streaming or not, as it asked), with usage summed.
Every request is logged to <logdir>/proxy.jsonl (one JSON object per request: budget, cut or not, thinking tokens/chars at the cut, times, tokens) so a trial's result.json can aggregate it.
usage: budget_proxy.py --listen <address of the subject network bridge>:18090 --upstream http://<model server>:8080 --model-map ... --logdir DIR [--continue-mode prefill|raw]
Python stdlib only (no npm, no extra packages)."""
import argparse, json, os, sys, threading, time, http.client, urllib.parse, socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

A = None            # parsed args
LOG_LOCK = threading.Lock()

def log_event(rec):
    rec["ts"] = round(time.time(), 3)
    with LOG_LOCK:
        with open(os.path.join(A.logdir, "proxy.jsonl"), "a") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def up_conn():
    u = urllib.parse.urlparse(A.upstream); return http.client.HTTPConnection(u.hostname, u.port or 80, timeout=A.upstream_timeout)

def sse_chunks(resp):
    """yield decoded `data:` payloads (str) from an SSE http response; '[DONE]' is yielded as the string"""
    buf = b""
    while True:
        line = resp.readline()
        if not line: break
        line = line.strip()
        if not line.startswith(b"data:"): continue
        yield line[5:].strip().decode("utf-8", "replace")

def build_continuation(body, reasoning, remaining):
    """request body that continues an assistant turn whose thinking was cut: same messages + the assistant's reasoning so far, thinking closed"""
    b = dict(body); b["stream"] = True; b["stream_options"] = {"include_usage": True}
    for k in ("max_tokens", "max_completion_tokens"): b.pop(k, None)
    b["max_tokens"] = max(16, remaining)
    if A.continue_mode == "prefill":      # verified on Spark/SGLang 2026-10-12: the chat template renders an assistant message whose *content* holds "<think>..</think>" and continue_final_message continues after it;
        # an assistant `reasoning_content` field is ignored by this server (the model starts thinking again), so the thinking goes into the content text.
        b["messages"] = list(body["messages"]) + [{"role": "assistant", "content": "<think>\n" + reasoning.strip("\n") + "\n</think>\n\n"}]
        b["continue_final_message"] = True; b["add_generation_prompt"] = False
    return b

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _send_json(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def _passthrough(self, method):
        n = int(self.headers.get("Content-Length") or 0); data = self.rfile.read(n) if n else None
        c = up_conn(); c.request(method, self.path, body=data, headers={"Content-Type": self.headers.get("Content-Type", "application/json")}); r = c.getresponse(); raw = r.read()
        self.send_response(r.status); self.send_header("Content-Type", r.getheader("Content-Type", "application/json")); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        try: self._passthrough("GET")
        except Exception as e: self._send_json(502, {"error": {"message": "upstream: %s" % e}})
    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            try: return self._passthrough("POST")
            except Exception as e: return self._send_json(502, {"error": {"message": "upstream: %s" % e}})
        n = int(self.headers.get("Content-Length") or 0); raw = self.rfile.read(n)
        try: body = json.loads(raw)
        except Exception: return self._send_json(400, {"error": {"message": "bad json"}})
        try: self.handle_chat(body)
        except ClientGone: pass
        except Exception as e:
            log_event({"error": "%s: %s" % (type(e).__name__, e)})
            try: self._send_json(502, {"error": {"message": "proxy: %s" % e}})
            except Exception: pass

    # ------------------------------------------------------------------
    def handle_chat(self, body):
        t0 = time.time(); client_stream = bool(body.get("stream"))
        budget = int(body.pop("reasoning_budget_tokens", None) or A.default_budget)
        limit = int(body.get("max_completion_tokens") or body.get("max_tokens") or A.default_limit)
        include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        up = dict(body); up["stream"] = True; up["stream_options"] = {"include_usage": True}
        rec = {"budget": budget, "limit": limit, "client_stream": client_stream, "model": body.get("model"), "tools": len(body.get("tools") or []), "cut": False, "effort": body.get("reasoning_effort"), "client_gone": False}
        out = Out(self, client_stream, include_usage, body)        # streaming clients get their headers at once and keepalive comments while the engine is silent
        conns = []
        try:
            c = up_conn(); conns.append(c); c.request("POST", self.path, body=json.dumps(up).encode(), headers={"Content-Type": "application/json"}); r = c.getresponse()
            if r.status != 200:
                raw = r.read(); rec.update(upstream_status=r.status)
                if out.started: out._emit({"error": {"message": "upstream HTTP %d: %s" % (r.status, raw[:200].decode("utf-8", "replace"))}}); out._emit("[DONE]")
                else:
                    self.send_response(r.status); self.send_header("Content-Type", r.getheader("Content-Type", "application/json")); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
                return
            state = {"reasoning": [], "n_reason": 0, "answered": False, "usage": None, "ttft": None, "first_id": None}
            cut = self.pump(r, out, state, budget, t0, can_cut=True)
            if cut:
                c.close()          # abandons the first generation on the engine
                t_cut = time.time() - t0
                rec.update(cut=True, thinking_tokens_at_cut=state["n_reason"], thinking_chars_at_cut=sum(len(x) for x in state["reasoning"]), seconds_to_cut=round(t_cut, 1))
                remaining = limit - state["n_reason"]
                c2 = up_conn(); conns.append(c2); cb = build_continuation(body, "".join(state["reasoning"]), remaining)
                c2.request("POST", self.path, body=json.dumps(cb).encode(), headers={"Content-Type": "application/json"}); r2 = c2.getresponse()
                if r2.status != 200:
                    err = r2.read(); rec.update(continuation_status=r2.status, continuation_error=err[:300].decode("utf-8", "replace")); out.finish_error(); return
                st2 = {"reasoning": [], "n_reason": 0, "answered": True, "usage": None, "ttft": None, "first_id": state["first_id"], "phase2": True}
                self.pump(r2, out, st2, 10 ** 9, t0, can_cut=False)
                u2 = st2["usage"] or {}
                rec.update(continuation_prompt_tokens=u2.get("prompt_tokens"), continuation_completion_tokens=u2.get("completion_tokens"), continuation_reasoning_chars_after_cut=sum(len(x) for x in st2["reasoning"]),
                           seconds_cut_to_first_token=(round(st2["ttft"] - t_cut, 1) if st2["ttft"] is not None else None))
                usage = {"prompt_tokens": max(0, (u2.get("prompt_tokens") or 0) - state["n_reason"]), "completion_tokens": state["n_reason"] + (u2.get("completion_tokens") or 0)}
            else:
                u = state["usage"] or {}; usage = {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens")}
                rec.update(thinking_tokens=state["n_reason"], thinking_chars=sum(len(x) for x in state["reasoning"]))
            usage["total_tokens"] = (usage.get("prompt_tokens") or 0) + (usage.get("completion_tokens") or 0)
            out.end(usage)
            rec.update(usage=usage, finish=out.finish_reason, has_tool_calls=out.has_tools, answer_chars=out.content_chars, ttft=state["ttft"], matched_stop=state.get("matched_stop"))
        except ClientGone:
            rec["client_gone"] = True; rec["client_gone_phase"] = "continuation" if rec.get("cut") else "first_stream"; rec["client_gone_after_s"] = round(time.time() - t0, 1); rec["since_last_write_s"] = round(time.time() - out.last_write, 1)
        except (OSError, http.client.HTTPException) as e:      # upstream side (reset, incomplete read, timeout): the client stream is cut, so say so loudly
            rec["upstream_error"] = "%s: %s" % (type(e).__name__, e); rec["upstream_error_phase"] = "continuation" if rec.get("cut") else "first_stream"; rec["upstream_error_after_s"] = round(time.time() - t0, 1)
            import traceback; sys.stderr.write("UPSTREAM ERROR %s\n%s\n" % (rec["upstream_error"], traceback.format_exc())); sys.stderr.flush()
        finally:      # always close the upstream connections: a closed connection aborts the generation on the engine (no orphan requests)
            out.close()
            for cc in conns:
                try: cc.close()
                except Exception: pass
            rec.update(seconds=round(time.time() - t0, 2), keepalives=out.keepalives)
            log_event(rec)

    def pump(self, resp, out, state, budget, t0, can_cut):
        """forward chunks of one upstream response; returns True when the thinking budget was reached and the stream was abandoned"""
        for payload in sse_chunks(resp):
            if payload == "[DONE]": break
            try: ch = json.loads(payload)
            except Exception: continue
            if ch.get("usage") and not ch.get("choices"): state["usage"] = ch["usage"]; continue
            if state["first_id"] is None: state["first_id"] = ch.get("id")
            choice = (ch.get("choices") or [{}])[0]; delta = choice.get("delta") or {}
            if choice.get("matched_stop") is not None: state["matched_stop"] = choice["matched_stop"]      # log only (SGLang: the stop token / string that ended the generation); nothing forwarded differently
            rc = delta.get("reasoning_content") or delta.get("reasoning")
            if state["ttft"] is None and (rc or delta.get("content") or delta.get("tool_calls")): state["ttft"] = round(time.time() - t0, 3)
            if delta.get("content") or delta.get("tool_calls"): state["answered"] = True
            if rc:
                state["reasoning"].append(rc); state["n_reason"] += 1
            out.chunk(ch, state)
            if can_cut and not state["answered"] and state["n_reason"] >= budget and not choice.get("finish_reason"): return True
            if choice.get("finish_reason"): out.finish_reason = choice["finish_reason"]
        return False

class ClientGone(Exception):
    pass

class Out:
    """what the client receives: SSE if it asked for a stream, else one assembled chat.completion.
    Writes are serialized (a keepalive thread may write too). A failed write marks the client as gone and raises ClientGone, so the caller can close the upstream stream (aborts the generation on the engine)."""
    KEEPALIVE_S = 10
    def __init__(self, h, stream, include_usage, body):
        self.h = h; self.stream = stream; self.include_usage = include_usage; self.body = body; self.started = False
        self.id = None; self.created = int(time.time()); self.model = body.get("model"); self.finish_reason = None; self.has_tools = False; self.content_chars = 0
        self.content = []; self.reasoning = []; self.tools = {}
        self.lock = threading.Lock(); self.gone = False; self.last_write = time.time(); self.keepalives = 0; self._stop = threading.Event()
        if stream:      # headers go out at once and ': keepalive' comment lines follow while the engine is silent (long prefill, or the re-prefill after a cut), so the client's idle timeout never fires
            self._start_headers()
            threading.Thread(target=self._keepalive, daemon=True).start()
    def _start_headers(self):
        with self.lock:
            if self.started: return
            self.h.send_response(200); self.h.send_header("Content-Type", "text/event-stream"); self.h.send_header("Cache-Control", "no-cache"); self.h.send_header("Connection", "close"); self.h.end_headers(); self.started = True
            self.h.wfile.flush(); self.last_write = time.time()
    def _write(self, raw):
        with self.lock:
            if self.gone: raise ClientGone()
            try: self.h.wfile.write(raw); self.h.wfile.flush(); self.last_write = time.time()
            except (BrokenPipeError, ConnectionResetError, OSError):
                self.gone = True; raise ClientGone()
    def _keepalive(self):
        while not self._stop.wait(2):
            if self.gone: return
            if time.time() - self.last_write >= self.KEEPALIVE_S:
                try: self._write(b": keepalive\n\n"); self.keepalives += 1
                except ClientGone: return
    def close(self): self._stop.set()
    def check_alive(self):
        if self.gone: raise ClientGone()
        if not self.stream:      # non-streaming client: nothing is written until the end, so look at the socket
            try:
                import select, socket
                r, _, _ = select.select([self.h.connection], [], [], 0)
                if r and self.h.connection.recv(1, socket.MSG_PEEK) == b"": self.gone = True; raise ClientGone()
            except ClientGone: raise
            except Exception: pass
    def _emit(self, obj):
        self._write(b"data: " + (obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)).encode() + b"\n\n")
    def chunk(self, ch, state):
        if self.id is None: self.id = ch.get("id"); self.created = ch.get("created", self.created); self.model = ch.get("model", self.model)
        ch = dict(ch); ch["id"] = self.id; ch["created"] = self.created
        choice = (ch.get("choices") or [{}])[0]; d = choice.get("delta") or {}
        if d.get("content"): self.content.append(d["content"]); self.content_chars += len(d["content"])
        rc = d.get("reasoning_content") or d.get("reasoning")
        if rc: self.reasoning.append(rc)
        for tc in d.get("tool_calls") or []:
            self.has_tools = True; t = self.tools.setdefault(tc.get("index", 0), {"id": None, "name": "", "arguments": ""})
            if tc.get("id"): t["id"] = tc["id"]
            f = tc.get("function") or {}
            if f.get("name"): t["name"] += f["name"]
            if f.get("arguments"): t["arguments"] += f["arguments"]
        if choice.get("finish_reason"): self.finish_reason = choice["finish_reason"]
        if self.stream: self._emit(ch)
        else: self.check_alive()
    def finish_error(self):
        if self.stream: self._emit("[DONE]")
        else: self.h._send_json(502, {"error": {"message": "continuation failed"}})
    def end(self, usage):
        self.close()
        if self.stream:
            if self.include_usage: self._emit({"id": self.id, "object": "chat.completion.chunk", "created": self.created, "model": self.model, "choices": [], "usage": usage})
            self._emit("[DONE]")
        else:
            msg = {"role": "assistant", "content": "".join(self.content) or None}
            if self.reasoning: msg["reasoning_content"] = "".join(self.reasoning)
            if self.tools: msg["tool_calls"] = [{"id": t["id"], "type": "function", "function": {"name": t["name"], "arguments": t["arguments"]}} for _, t in sorted(self.tools.items())]
            self.h._send_json(200, {"id": self.id, "object": "chat.completion", "created": self.created, "model": self.model, "choices": [{"index": 0, "message": msg, "finish_reason": self.finish_reason or "stop"}], "usage": usage})

class Server(ThreadingHTTPServer):
    daemon_threads = True; allow_reuse_address = True

def main():
    global A
    ap = argparse.ArgumentParser(); ap.add_argument("--listen", required=True); ap.add_argument("--upstream", required=True); ap.add_argument("--logdir", required=True)
    ap.add_argument("--default-budget", type=int, default=8192); ap.add_argument("--default-limit", type=int, default=16384); ap.add_argument("--upstream-timeout", type=int, default=1800); ap.add_argument("--continue-mode", default="prefill", choices=["prefill"])
    A = ap.parse_args(); os.makedirs(A.logdir, exist_ok=True)
    host, port = A.listen.rsplit(":", 1); srv = Server((host, int(port)), Handler)
    print("budget_proxy listening on %s -> %s (budget %d, limit %d, mode %s)" % (A.listen, A.upstream, A.default_budget, A.default_limit, A.continue_mode), flush=True)
    srv.serve_forever()
if __name__ == "__main__": main()
