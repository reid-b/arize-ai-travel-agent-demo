import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from anywhere

import json
from tools import web as ws

def run(q="Tokyo travel tips spring"): return json.loads(ws.web_search.invoke({"query": q}))

# 1) first backend works
ws._search_ddgs = lambda q, b: [ws.WebResult(title="T", snippet="s", url="http://x")]
r = run(); assert r["status"]=="ok" and r["source"]=="ddgs:auto", r

# 2) rate-limited twice then works
calls=[]
def flaky(q,b):
    calls.append(b)
    if len(calls)<3: raise RuntimeError("Ratelimit 202")
    return [ws.WebResult(title="T", snippet="s")]
ws._search_ddgs = flaky
r = run(); assert r["status"]=="ok" and r["source"]=="ddgs:bing" and len(r["attempts"])==2, r

# 3) all engines fail -> wikivoyage fallback
def boom(q,b): raise RuntimeError("blocked")
ws._search_ddgs = boom
class Resp:
    def raise_for_status(self): pass
    def json(self): return {"query":{"pages":{"1":{"title":"Tokyo","index":1,"extract":"Tokyo is the capital."}}}}
ws.requests.get = lambda *a, **k: Resp()
r = run(); assert r["status"]=="ok" and r["source"]=="wikivoyage" and r["results"][0]["url"].endswith("/Tokyo"), r
assert len(r["attempts"])==3

# 4) everything fails -> error as data with reasons
def down(*a, **k): raise ConnectionError("offline")
ws.requests.get = down
r = run(); assert r["status"]=="error" and "offline" in r["error"] and "blocked" in r["error"], r

# 5) everything empty -> no_results
ws._search_ddgs = lambda q,b: []
class Empty(Resp):
    def json(self): return {}
ws.requests.get = lambda *a, **k: Empty()
r = run(); assert r["status"]=="no_results" and r["error"] is None, r

# 6) empty query
assert run("  ")["status"]=="error"
print("ALL PASS")
