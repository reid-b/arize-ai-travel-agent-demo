"""Arize Phoenix tracing for the Sojourns agent.

Call setup_tracing() once, before the agent is built. It registers Phoenix as the
OpenTelemetry trace destination and auto-instruments LangChain/LangGraph through the
OpenInference instrumentor, so every agent run shows up as a trace: LLM calls, tool
calls and graph steps.

Configuration (all optional, via environment / .env):
  PHOENIX_PROJECT_NAME        project name in Phoenix (default "sojourns")
  PHOENIX_COLLECTOR_ENDPOINT  OTLP HTTP traces URL; unset = local Phoenix on :6006
  PHOENIX_API_KEY             only if the Phoenix deployment has auth enabled
  PHOENIX_TRACING=0           turn tracing off

Tracing must never break the app: if the packages are missing or Phoenix is not
running, the agent still works, just without traces. Phoenix is probed once at startup
so a missing server produces one clear message instead of a stream of export retries.
"""

import os
import urllib.error
import urllib.request


def _phoenix_reachable() -> tuple[bool, str]:
    """True if something answers at the Phoenix endpoint (any HTTP status counts)."""
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    try:
        urllib.request.urlopen(endpoint, timeout=2)
    except urllib.error.HTTPError:
        return True, endpoint   # server answered, even if with 401/404
    except Exception:
        return False, endpoint
    return True, endpoint


def setup_tracing():
    if os.getenv("PHOENIX_TRACING", "1") == "0":
        print("[sojourns] Tracing disabled (PHOENIX_TRACING=0).", flush=True)
        return None
    ok, endpoint = _phoenix_reachable()
    if not ok:
        print(f"[sojourns] Phoenix isn't reachable at {endpoint}; tracing is off for this run. "
              "Start Phoenix, then restart Sojourns.", flush=True)
        return None
    try:
        from phoenix.otel import register

        provider = register(
            project_name=os.getenv("PHOENIX_PROJECT_NAME", "sojourns"),
            protocol="http/protobuf",
            auto_instrument=True,  # picks up openinference-instrumentation-langchain
        )
        print("[sojourns] Tracing on. View traces in Phoenix (default http://localhost:6006).",
              flush=True)
        return provider
    except ImportError:
        print("[sojourns] Tracing packages not installed; running without traces. "
              "Install: pip install arize-phoenix-otel openinference-instrumentation-langchain",
              flush=True)
    except Exception as e:  # never let observability take the app down
        print(f"[sojourns] Tracing setup failed ({type(e).__name__}: {e}); running without traces.",
              flush=True)
    return None
