#!/bin/sh
# Wait (up to 60s) for Phoenix before starting the app. tracing.py probes Phoenix once at
# startup, so starting too early would turn tracing off for the whole run.
set -e

if [ -n "$PHOENIX_COLLECTOR_ENDPOINT" ] && [ "$PHOENIX_TRACING" != "0" ]; then
  python - "$PHOENIX_COLLECTOR_ENDPOINT" <<'PY'
import sys, time, urllib.error, urllib.request

endpoint = sys.argv[1]
for _ in range(60):
    try:
        urllib.request.urlopen(endpoint, timeout=2)
        print(f"[sojourns] Phoenix is up at {endpoint}", flush=True)
        break
    except urllib.error.HTTPError:
        print(f"[sojourns] Phoenix is up at {endpoint}", flush=True)
        break
    except Exception:
        time.sleep(1)
else:
    print(f"[sojourns] Phoenix not reachable at {endpoint}; starting without waiting.", flush=True)
PY
fi

exec "$@"
