import json
import os
import signal
import threading
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel

load_dotenv()

from tracing import setup_tracing  # noqa: E402

setup_tracing()  # must run before the agent is built so LangChain/LangGraph are instrumented

from agent import build_agent  # noqa: E402

agent = build_agent()

app = FastAPI(
    title="LangGraph Agent API",
    description="A simple API for interacting with a LangGraph agent that can search the web",
    version="0.1.0",
)

STATIC_DIR = Path(__file__).parent / "static"

# --- Auto-shutdown when the last browser tab closes -------------------------
# Enabled only when SOJOURNS_AUTOSHUTDOWN=1 (the desktop launcher sets it), so
# normal `uvicorn api:app --reload` development is unaffected.
AUTO_SHUTDOWN = os.getenv("SOJOURNS_AUTOSHUTDOWN") == "1"
GRACE_SECONDS = 5  # wait this long so a page refresh doesn't stop the server

_sessions: set[str] = set()
_lock = threading.Lock()
_timer: threading.Timer | None = None


def _shutdown_if_idle() -> None:
    with _lock:
        if _sessions:
            return
    print("[sojourns] No open tabs. Stopping the server...", flush=True)
    os.kill(os.getpid(), signal.SIGINT)  # uvicorn shuts down gracefully on SIGINT


class SessionEvent(BaseModel):
    id: str


@app.post("/session/open", include_in_schema=False)
def session_open(event: SessionEvent):
    global _timer
    with _lock:
        _sessions.add(event.id)
        if _timer is not None:
            _timer.cancel()
            _timer = None
            print("[sojourns] Tab is back. Shutdown cancelled.", flush=True)
    return {"ok": True}


@app.post("/session/close", include_in_schema=False)
def session_close(event: SessionEvent):
    global _timer
    with _lock:
        _sessions.discard(event.id)
        if AUTO_SHUTDOWN and not _sessions:
            if _timer is not None:
                _timer.cancel()
            print(f"[sojourns] Tab closed. Shutting down in {GRACE_SECONDS}s "
                  "(reopen the page to cancel).", flush=True)
            _timer = threading.Timer(GRACE_SECONDS, _shutdown_if_idle)
            _timer.daemon = True
            _timer.start()
    return {"ok": True}


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Turn] = []  # optional: prior turns, oldest first
    session_id: str | None = None  # groups a conversation's traces in Phoenix


class ChatResponse(BaseModel):
    response: str
    tools_used: list[str] = []  # names of tools the agent called this turn
    reports: list[dict] = []  # structured compare_destinations results, drawn as charts by the UI


@app.get("/", include_in_schema=False)
def index():
    """Serve the Sojourns front end."""
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Send a message to the agent and get a response."""
    prior = [
        HumanMessage(content=t.content) if t.role == "user" else AIMessage(content=t.content)
        for t in request.history
    ]
    messages = prior + [HumanMessage(content=request.message)]
    try:
        config = {"metadata": {"session_id": request.session_id}} if request.session_id else {}
        result = agent.invoke({"messages": messages}, config=config)
    except Exception as e:
        print(f"[sojourns] agent error: {type(e).__name__}: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    # Tool calls the agent made during this turn (messages after the ones we sent).
    tools_used: list[str] = []
    reports: list[dict] = []
    call_names: dict[str, str] = {}
    for m in result["messages"][len(messages):]:
        if isinstance(m, AIMessage):
            for call in m.tool_calls:
                call_names[call["id"]] = call["name"]
                if call["name"] not in tools_used:
                    tools_used.append(call["name"])
        elif isinstance(m, ToolMessage) and call_names.get(m.tool_call_id) == "compare_destinations":
            try:
                data = json.loads(m.content)
            except (TypeError, ValueError):
                continue
            if isinstance(data, dict) and data.get("status") in ("ok", "partial"):
                reports.append(data)

    return ChatResponse(response=result["messages"][-1].content, tools_used=tools_used, reports=reports)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}
