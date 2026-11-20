"""Flight search tool for the Sojourns travel agent, backed by the Duffel API.

The tool returns a JSON document with a fixed schema (see FlightSearchResult) so
the agent, tests and any UI can rely on stable field names. Errors are returned
as data (status="error") instead of raised, so the agent can read them and recover.
"""

import os
from datetime import datetime
from typing import Literal

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel

load_dotenv()

DUFFEL_OFFER_REQUESTS_URL = "https://api.duffel.com/air/offer_requests"
MAX_RESULTS = 5  # keep tool output small for the model's context window


# ---- Output schema ---------------------------------------------------------
class Flight(BaseModel):
    offer_id: str
    airline: str
    flight_number: str
    departs: str            # ISO 8601 local time, e.g. "2026-12-20T07:15:00"
    arrives: str            # ISO 8601 local time
    duration: str | None    # ISO 8601 duration, e.g. "PT5H30M"
    stops: int
    price: float
    currency: str


class FlightSearchResult(BaseModel):
    status: Literal["ok", "no_results", "error"]
    source: str = "duffel"
    data_mode: Literal["test", "live", "unknown"] = "unknown"
    origin: str
    destination: str
    date: str
    flights: list[Flight] = []   # cheapest first, at most MAX_RESULTS
    error: str | None = None


def _data_mode() -> str:
    token = os.getenv("DUFFEL_API_KEY", "")
    if token.startswith("duffel_test_"):
        return "test"
    if token.startswith("duffel_live_"):
        return "live"
    return "unknown"


def _fetch_flights(
    origin: str, destination: str, date: str, adults: int = 1, cabin: str = "economy"
) -> list[Flight]:
    """Call Duffel and return typed offers, cheapest first."""
    token = os.getenv("DUFFEL_API_KEY")
    if not token:
        raise RuntimeError("DUFFEL_API_KEY is not set")

    response = requests.post(
        DUFFEL_OFFER_REQUESTS_URL,
        params={"return_offers": "true"},
        headers={
            "Authorization": f"Bearer {token}",
            "Duffel-Version": "v2",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={
            "data": {
                "slices": [
                    {"origin": origin, "destination": destination, "departure_date": date}
                ],
                "passengers": [{"type": "adult"} for _ in range(adults)],
                "cabin_class": cabin,
            }
        },
        timeout=30,
    )
    response.raise_for_status()

    flights = []
    for offer in response.json()["data"]["offers"]:
        slice_ = offer["slices"][0]
        segments = slice_["segments"]
        first, last = segments[0], segments[-1]
        flights.append(
            Flight(
                offer_id=offer["id"],
                airline=first["operating_carrier"]["name"],
                flight_number=(
                    f"{first['marketing_carrier']['iata_code']}"
                    f"{first['marketing_carrier_flight_number']}"
                ),
                departs=first["departing_at"],
                arrives=last["arriving_at"],
                duration=slice_.get("duration"),
                stops=len(segments) - 1,
                price=float(offer["total_amount"]),
                currency=offer["total_currency"],
            )
        )
    return sorted(flights, key=lambda f: f.price)[:MAX_RESULTS]


def _result(status, origin, destination, date, flights=None, error=None) -> str:
    return FlightSearchResult(
        status=status,
        data_mode=_data_mode(),
        origin=origin,
        destination=destination,
        date=date,
        flights=flights or [],
        error=error,
    ).model_dump_json()


# ---- The tool --------------------------------------------------------------
@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search one-way flights between two airports on a given date.

    Use this for any question about flight options, times or prices. Do not use web
    search for fares.

    Args:
        origin: 3-letter IATA airport code, e.g. "JFK".
        destination: 3-letter IATA airport code, e.g. "LAX".
        date: Departure date in YYYY-MM-DD format. Must be today or later.

    Returns:
        A JSON object: {status: "ok"|"no_results"|"error", data_mode: "test"|"live",
        origin, destination, date, flights: [{offer_id, airline, flight_number,
        departs, arrives, duration, stops, price, currency}], error}.
        Flights are sorted cheapest first. data_mode "test" means sandbox data, not
        real fares.
    """
    origin, destination = origin.upper().strip(), destination.upper().strip()

    if len(origin) != 3 or len(destination) != 3 or not (origin + destination).isalpha():
        return _result("error", origin, destination, date,
                       error="origin and destination must be 3-letter IATA airport codes")
    try:
        parsed = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return _result("error", origin, destination, date,
                       error="date must be in YYYY-MM-DD format")
    today = datetime.now().date()
    if parsed < today:
        return _result("error", origin, destination, date,
                       error=f"{date} is in the past; today is {today.isoformat()}")

    try:
        flights = _fetch_flights(origin, destination, date)
    except requests.HTTPError as e:
        try:
            errs = e.response.json().get("errors", [])
            detail = "; ".join(x.get("message", "") for x in errs) or e.response.text[:300]
        except ValueError:
            detail = e.response.text[:300]
        return _result("error", origin, destination, date,
                       error=f"Duffel returned {e.response.status_code}: {detail}")
    except Exception as e:
        return _result("error", origin, destination, date,
                       error=f"{type(e).__name__}: {e}")

    status = "ok" if flights else "no_results"
    return _result(status, origin, destination, date, flights=flights)


if __name__ == "__main__":
    # Quick manual test:  python -m tools.flights
    print(search_flights.invoke({"origin": "JFK", "destination": "LAX", "date": "2026-12-20"}))
