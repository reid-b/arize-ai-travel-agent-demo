"""Car rental search tool for the Sojourns travel agent.

Data source: OctoTrip's free rental-car search service (https://github.com/octotrip/rental-cars).
It is a hosted MCP server (stateless Streamable HTTP, JSON-RPC, no API key). We call it
directly with `requests`, so no MCP client library is needed:

    POST https://mcp.octotrip.app/rental-cars/mcp
      1. initialize
      2. tools/call  name="search"  arguments={location, pickup_date, dropoff_date, ...}

Like the other tools, this one returns a JSON document with a fixed schema and reports
errors as data (status="error"), so the agent can read them and recover.

Notes on the source (from its README):
  * It queries several rental providers live and returns the cheapest two offers per car
    category. Rate limit: 1 request/second, burst of 5.
  * It is free; booking links may carry affiliate attribution, and results are ranked by
    price, not payout. Both facts are passed through in `note`.
  * It does not book anything.
"""

import json
from datetime import datetime
from typing import Any, Literal

import requests
from langchain_core.tools import tool
from pydantic import BaseModel

MCP_URL = "https://mcp.octotrip.app/rental-cars/mcp"
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
MAX_RESULTS = 6  # keep tool output small for the model's context window
AFFILIATE_NOTE = (
    "Booking links may carry affiliate attribution. Results are ranked by price, "
    "not by affiliate payout."
)


# ---- Output schema ---------------------------------------------------------
class CarOffer(BaseModel):
    name: str                       # e.g. "VW Polo or similar"
    vendor: str | None = None       # rental company
    category: str | None = None     # e.g. "Economy", "SUV"
    transmission: str | None = None
    passengers: Any = None
    bags: Any = None
    air_con: Any = None
    fuel_policy: str | None = None
    mileage: str | None = None
    free_cancellation: Any = None
    deposit: Any = None
    price_total: float | None = None
    price_per_day: float | None = None
    currency: str | None = None
    booking_url: str | None = None


class CarRentalResult(BaseModel):
    status: Literal["ok", "no_results", "error"]
    source: str = "octotrip"
    pickup_location: str             # what the user asked for
    resolved_pickup: str | None = None
    resolved_dropoff: str | None = None
    pickup_date: str
    dropoff_date: str
    rental_days: int | None = None
    currency: str
    offers: list[CarOffer] = []      # cheapest first, at most MAX_RESULTS
    total_available: int | None = None
    note: str | None = None
    error: str | None = None


# ---- MCP over HTTP ---------------------------------------------------------
def _parse_rpc(body: str, content_type: str) -> dict:
    """Parse a JSON-RPC reply that may arrive as plain JSON or as a text/event-stream."""
    if "text/event-stream" in content_type or body.lstrip().startswith(("event:", "data:")):
        for line in body.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if not chunk:
                    continue
                try:
                    msg = json.loads(chunk)
                except ValueError:
                    continue
                if isinstance(msg, dict) and ("result" in msg or "error" in msg):
                    return msg
        raise ValueError("no JSON-RPC message found in the event stream")
    return json.loads(body)


def _rpc(method: str, params: dict, rpc_id: int) -> dict:
    resp = requests.post(
        MCP_URL,
        headers=MCP_HEADERS,
        json={"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params},
        timeout=60,
    )
    resp.raise_for_status()
    msg = _parse_rpc(resp.text, resp.headers.get("Content-Type", ""))
    if "error" in msg:
        err = msg["error"]
        raise RuntimeError(err.get("message", str(err)) if isinstance(err, dict) else str(err))
    return msg["result"]


def _call_search(arguments: dict) -> Any:
    """Run the service's `search` tool and return its payload (parsed JSON if possible)."""
    _rpc("initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "sojourns", "version": "0.1"},
    }, 1)
    result = _rpc("tools/call", {"name": "search", "arguments": arguments}, 2)
    if result.get("structuredContent"):
        return _unwrap(result["structuredContent"])
    text = "".join(
        c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"
    )
    return _unwrap(text)


# ---- Response parsing (defensive: the exact nesting isn't documented) ------
def _unwrap(data):
    """The service nests its answer: {"result": "<json text>"}. Peel that off.

    Observed live: structuredContent == {"result": "{\\n  \\"error\\": \\"no_results\\", ...}"}.
    Handles JSON text, and a {"result": ...} wrapper, up to a few levels deep.
    """
    for _ in range(4):
        if isinstance(data, str):
            try:
                data = json.loads(data)
                continue
            except ValueError:
                return {"_text": data}
        if isinstance(data, dict) and "result" in data and set(data) <= {"result", "isError"}:
            data = data["result"]
            continue
        break
    return data


def _num(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _s(x) -> str | None:
    return None if x is None else str(x)


def _collect_offers(node, out: list[dict]) -> None:
    """Offers are grouped by category; find every dict that looks like an offer."""
    if isinstance(node, dict):
        if "price" in node and "name" in node:
            out.append(node)
        else:
            for v in node.values():
                _collect_offers(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_offers(v, out)


def _to_offer(o: dict) -> CarOffer:
    return CarOffer(
        name=str(o.get("name", "Unnamed car")),
        vendor=_s(o.get("vendor")),
        category=_s(o.get("category")),
        transmission=_s(o.get("transmission")),
        passengers=o.get("passengers"),
        bags=o.get("bags"),
        air_con=o.get("air_con"),
        fuel_policy=_s(o.get("fuel_policy")),
        mileage=_s(o.get("mileage")),
        free_cancellation=o.get("free_cancellation"),
        deposit=o.get("deposit"),
        price_total=_num(o.get("price")),
        price_per_day=_num(o.get("price_per_day")),
        currency=_s(o.get("currency")),
        booking_url=_s(o.get("booking_url")),
    )


# ---- The tool --------------------------------------------------------------
@tool
def search_car_rentals(
    location: str,
    pickup_date: str,
    dropoff_date: str,
    dropoff_location: str | None = None,
    driver_age: int = 30,
    currency: str = "USD",
) -> str:
    """Search rental cars at a pickup location for a range of dates.

    Use this for any question about renting a car. Do not use web search for rental prices.

    Args:
        location: Pickup airport, city, station or landmark, e.g. "LAX" or "Munich Airport".
            Airports work best; if a city returns no results, retry with its airport code.
        pickup_date: Pickup date, YYYY-MM-DD. Today or later.
        dropoff_date: Drop-off date, YYYY-MM-DD. After the pickup date.
        dropoff_location: Only for one-way rentals; defaults to the pickup location.
        driver_age: Driver's age (18 or older; default 30). Younger drivers may pay surcharges.
        currency: 3-letter currency code for prices (default "USD").

    Returns:
        A JSON object: {status: "ok"|"no_results"|"error", source, pickup_location,
        resolved_pickup, resolved_dropoff, pickup_date, dropoff_date, rental_days, currency,
        offers: [{name, vendor, category, transmission, passengers, bags, air_con,
        fuel_policy, mileage, free_cancellation, deposit, price_total, price_per_day,
        currency, booking_url}], total_available, note, error}. Offers are sorted cheapest
        first. For status "no_results", note holds the service's own message and suggestions.
        This tool only searches; it cannot book.
    """
    location = location.strip()
    currency = currency.strip().upper() or "USD"

    def result(status, offers=None, parsed=None, error=None, note=None):
        parsed = parsed or {}
        return CarRentalResult(
            status=status, pickup_location=location,
            resolved_pickup=_s(parsed.get("pickup_location_resolved")),
            resolved_dropoff=_s(parsed.get("dropoff_location_resolved")),
            pickup_date=pickup_date, dropoff_date=dropoff_date,
            rental_days=parsed.get("rental_days") if isinstance(parsed.get("rental_days"), int) else None,
            currency=currency, offers=offers or [],
            total_available=parsed.get("total_available") if isinstance(parsed.get("total_available"), int) else None,
            note=note if note is not None else (AFFILIATE_NOTE if status == "ok" else None),
            error=error,
        ).model_dump_json()

    # -- validate locally before spending a rate-limited request --
    if not location:
        return result("error", error="location is required")
    if len(currency) != 3 or not currency.isalpha():
        return result("error", error="currency must be a 3-letter code like USD")
    if driver_age < 18:
        return result("error", error="driver_age must be 18 or older")
    try:
        d_pick = datetime.strptime(pickup_date, "%Y-%m-%d").date()
        d_drop = datetime.strptime(dropoff_date, "%Y-%m-%d").date()
    except ValueError:
        return result("error", error="pickup_date and dropoff_date must be in YYYY-MM-DD format")
    today = datetime.now().date()
    if d_pick < today:
        return result("error", error=f"pickup_date {pickup_date} is in the past; today is {today.isoformat()}")
    if d_drop <= d_pick:
        return result("error", error="dropoff_date must be after pickup_date")

    arguments = {
        "location": location,
        "pickup_date": pickup_date,
        "dropoff_date": dropoff_date,
        "age": driver_age,
        "currency": currency,
    }
    if dropoff_location and dropoff_location.strip():
        arguments["dropoff_location"] = dropoff_location.strip()

    try:
        data = _call_search(arguments)
    except requests.HTTPError as e:
        return result("error", error=f"rental service returned HTTP {e.response.status_code}")
    except requests.RequestException as e:
        return result("error", error=f"couldn't reach the rental service: {type(e).__name__}")
    except Exception as e:
        return result("error", error=f"{type(e).__name__}: {e}")

    parsed = data if isinstance(data, dict) else {}

    # The service reports problems as {error: "location_not_found" | "invalid_date" | "no_results", ...}
    err = parsed.get("error") if parsed else None
    if err:
        label = (err.get("type") or err.get("code") or err.get("message")) if isinstance(err, dict) else str(err)
        message = parsed.get("message") or (err.get("message") if isinstance(err, dict) else None)
        hints = (parsed.get("suggestions") or parsed.get("suggestion")
                 or (err.get("suggestions") if isinstance(err, dict) else None))
        detail = str(label)
        if message and message != label:
            detail += f": {message}"
        if hints:
            detail += f" (suggestions: {hints})"
        print(f"[sojourns] car rental service replied: {json.dumps(data)[:600]}", flush=True)
        if "no_results" in str(label):
            return result("no_results", parsed=parsed, note=detail)
        return result("error", parsed=parsed, error=detail)

    raw: list[dict] = []
    _collect_offers(data, raw)
    offers = sorted(
        (_to_offer(o) for o in raw),
        key=lambda c: (c.price_total is None, c.price_total or 0),
    )[:MAX_RESULTS]

    if offers:
        return result("ok", offers=offers, parsed=parsed)
    print(f"[sojourns] car rental service replied with no usable offers: {json.dumps(data)[:600]}", flush=True)
    if parsed.get("total_available") == 0:
        return result("no_results", parsed=parsed, note="The service found no rental cars for these dates and location.")
    preview = (parsed.get("_text") or json.dumps(data))[:300]
    return result("error", parsed=parsed,
                  error=f"unrecognized response from the rental service: {preview}")


if __name__ == "__main__":
    # Quick manual test:  python -m tools.cars
    from datetime import timedelta
    p = (datetime.now().date() + timedelta(days=30)).isoformat()
    d = (datetime.now().date() + timedelta(days=37)).isoformat()
    print(search_car_rentals.invoke({"location": "LAX", "pickup_date": p, "dropoff_date": d}))
