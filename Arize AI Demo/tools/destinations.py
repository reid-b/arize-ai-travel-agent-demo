"""Destination comparison tool for the Sojourns travel agent.

Builds a price comparison report across destinations and finds deals:

* It samples the cheapest fare on several departure dates per destination
  (a "price calendar") by reusing the Duffel flight search.
* Every observation is saved to a local history file, so the baseline for
  "what is a normal price on this route" gets better each time the tool runs.
* A date is flagged as a deal when its fare is at least DEAL_THRESHOLD below the
  route's baseline median.
* It suggests destinations with a similar feel (for example Amsterdam -> Berlin)
  from a small curated profile table and compares their prices to the anchor.

Honest limits: Duffel has no historical-fares endpoint, so "history" here is the
sampled calendar plus earlier runs saved on disk. In sandbox mode (duffel_test_
token) prices are synthetic, and the report says so.

Like the other tools, it returns a JSON document with a fixed schema and returns
errors as data instead of raising.
"""

import json
import os
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel

from .flights import _data_mode, _fetch_flights

HISTORY_FILE = Path(
    os.getenv("SOJOURNS_PRICE_HISTORY", Path(__file__).resolve().parent.parent / "data" / "price_history.json")
)
HISTORY_DAYS = 90          # how far back stored observations count toward the baseline
DEAL_THRESHOLD = 0.85      # a fare at or below 85% of the baseline median is a deal
MIN_BASELINE_OBS = 4       # fewer observations than this: no deal verdict
MAX_DESTINATIONS = 4
MAX_SEARCHES = 24          # hard cap on Duffel calls per report
WORKERS = 5

# ---- Destination profiles (curated, used for "similar experience") ----------
PROFILES: dict[str, dict] = {
    "AMS": {"city": "Amsterdam", "tags": {"canals", "bikes", "museums", "nightlife", "cafes", "art", "compact", "architecture"}},
    "BER": {"city": "Berlin", "tags": {"nightlife", "museums", "history", "street art", "bikes", "art", "cafes", "music"}},
    "PRG": {"city": "Prague", "tags": {"history", "architecture", "beer", "nightlife", "castles", "compact", "budget"}},
    "CPH": {"city": "Copenhagen", "tags": {"bikes", "design", "food", "canals", "cafes", "compact", "museums"}},
    "VIE": {"city": "Vienna", "tags": {"museums", "music", "architecture", "cafes", "history", "art"}},
    "BRU": {"city": "Brussels", "tags": {"beer", "architecture", "food", "museums", "compact", "art"}},
    "BUD": {"city": "Budapest", "tags": {"thermal baths", "nightlife", "architecture", "history", "budget", "river"}},
    "LIS": {"city": "Lisbon", "tags": {"hills", "food", "nightlife", "coast", "budget", "history", "trams"}},
    "OPO": {"city": "Porto", "tags": {"food", "wine", "budget", "coast", "hills", "history"}},
    "BCN": {"city": "Barcelona", "tags": {"beaches", "architecture", "nightlife", "food", "art"}},
    "FCO": {"city": "Rome", "tags": {"history", "food", "art", "museums", "architecture"}},
    "CDG": {"city": "Paris", "tags": {"museums", "art", "food", "architecture", "cafes"}},
    "LHR": {"city": "London", "tags": {"museums", "nightlife", "music", "history", "theatre"}},
    "DUB": {"city": "Dublin", "tags": {"pubs", "music", "history", "literature", "compact"}},
    "KRK": {"city": "Krakow", "tags": {"history", "budget", "beer", "compact", "architecture", "castles", "nightlife"}},
    "HAM": {"city": "Hamburg", "tags": {"canals", "music", "nightlife", "harbour", "architecture"}},
    "MUC": {"city": "Munich", "tags": {"beer", "castles", "mountains", "museums", "architecture"}},
    "ATH": {"city": "Athens", "tags": {"history", "food", "beaches", "budget", "architecture"}},
}
NAME_TO_IATA = {p["city"].lower(): code for code, p in PROFILES.items()}


# ---- Output schema -----------------------------------------------------------
class PriceSample(BaseModel):
    date: str
    price: float
    airline: str
    stops: int


class Deal(BaseModel):
    date: str
    price: float
    pct_below_baseline: float


class DestinationReport(BaseModel):
    iata: str
    city: str | None = None
    samples: list[PriceSample] = []     # cheapest fare per sampled date, by date
    failed_dates: list[str] = []
    cheapest_date: str | None = None
    cheapest_price: float | None = None
    median_price: float | None = None   # typical fare across the sampled dates
    baseline_price: float | None = None  # median of stored + sampled history
    baseline_observations: int = 0
    baseline_source: Literal["stored_history", "sampled_calendar", "none"] = "none"
    deals: list[Deal] = []              # best first
    verdict: Literal["deal", "typical", "insufficient_data"] = "insufficient_data"


class SimilarDestination(BaseModel):
    report: DestinationReport
    similar_to: str
    shared_traits: list[str]
    similarity: float                    # 0..1 (Jaccard overlap of traits)
    cheaper_than_anchor_pct: float | None = None  # positive = cheaper, by median fare


class ComparisonReport(BaseModel):
    status: Literal["ok", "partial", "error"]
    source: str = "duffel"
    data_mode: Literal["test", "live", "unknown"] = "unknown"
    origin: str
    currency: str | None = None
    window: list[str] = []               # the sampled departure dates
    destinations: list[DestinationReport] = []
    ranking: list[str] = []              # requested IATA codes, cheapest typical fare first
    similar: list[SimilarDestination] = []
    notes: list[str] = []
    error: str | None = None


# ---- Price history store -----------------------------------------------------
def _load_history() -> list[dict]:
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return []


def _save_history(records: list[dict]) -> bool:
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    kept = [r for r in records if r.get("observed_on", "") >= cutoff]
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = HISTORY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(kept))
        tmp.replace(HISTORY_FILE)
        return True
    except Exception:
        return False


def _merge(history: list[dict], new: list[dict]) -> list[dict]:
    """Add observations; one record per route, departure date and observation day."""
    by_key = {(r["origin"], r["destination"], r["depart_date"], r["observed_on"]): r for r in history}
    for r in new:
        by_key[(r["origin"], r["destination"], r["depart_date"], r["observed_on"])] = r
    return list(by_key.values())


# ---- Helpers -------------------------------------------------------------------
def similar_destinations(iata: str, exclude: set[str], limit: int = 3) -> list[tuple[str, float, list[str]]]:
    """Rank profiled destinations by trait overlap with `iata`."""
    base = PROFILES.get(iata)
    if not base:
        return []
    scored = []
    for code, prof in PROFILES.items():
        if code == iata or code in exclude:
            continue
        shared = base["tags"] & prof["tags"]
        union = base["tags"] | prof["tags"]
        score = len(shared) / len(union)
        if shared:
            scored.append((code, round(score, 2), sorted(shared)))
    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


def _resolve(value: str) -> str | None:
    v = value.strip()
    if len(v) == 3 and v.isalpha():
        return v.upper()
    return NAME_TO_IATA.get(v.lower())


def _sample_one(origin: str, dest: str, day: str):
    try:
        flights = _fetch_flights(origin, dest, day)
    except Exception as e:  # network, HTTP, auth: reported as data
        return day, None, f"{type(e).__name__}: {str(e)[:120]}"
    if not flights:
        return day, None, "no flights"
    return day, flights[0], None   # _fetch_flights sorts cheapest first


def _build_report(origin, dest, results, history, today_iso) -> tuple[DestinationReport, list[dict], str | None]:
    """Turn raw samples for one destination into a report plus new history records."""
    samples, failed, new_records, currency = [], [], [], None
    for day, flight, err in sorted(results, key=lambda r: r[0]):
        if flight is None:
            failed.append(day)
            continue
        currency = currency or flight.currency
        samples.append(PriceSample(date=day, price=flight.price, airline=flight.airline, stops=flight.stops))
        new_records.append({"origin": origin, "destination": dest, "depart_date": day,
                            "price": flight.price, "currency": flight.currency,
                            "observed_on": today_iso})

    merged = _merge(history, new_records)
    cutoff = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    pool = [r for r in merged if r["origin"] == origin and r["destination"] == dest
            and r["observed_on"] >= cutoff and (currency is None or r["currency"] == currency)]
    prices = [s.price for s in samples]

    report = DestinationReport(
        iata=dest,
        city=PROFILES.get(dest, {}).get("city"),
        samples=samples,
        failed_dates=failed,
    )
    if prices:
        cheapest = min(samples, key=lambda s: s.price)
        report.cheapest_date, report.cheapest_price = cheapest.date, cheapest.price
        report.median_price = round(statistics.median(prices), 2)

    report.baseline_observations = len(pool)
    if len(pool) >= MIN_BASELINE_OBS and prices:
        baseline = statistics.median(r["price"] for r in pool)
        report.baseline_price = round(baseline, 2)
        earlier = {r["observed_on"] for r in pool} - {today_iso}
        report.baseline_source = "stored_history" if earlier else "sampled_calendar"
        deals = [Deal(date=s.date, price=s.price,
                      pct_below_baseline=round((1 - s.price / baseline) * 100, 1))
                 for s in samples if s.price <= baseline * DEAL_THRESHOLD]
        report.deals = sorted(deals, key=lambda d: -d.pct_below_baseline)
        report.verdict = "deal" if report.deals else "typical"
    return report, new_records, currency


def _error(origin, message, **kw) -> str:
    return ComparisonReport(status="error", data_mode=_data_mode(), origin=origin,
                            error=message, **kw).model_dump_json()


# ---- The tool ------------------------------------------------------------------
@tool
def compare_destinations(
    origin: str,
    destinations: list[str],
    start_date: str = "",
    num_dates: int = 4,
    include_similar: bool = True,
) -> str:
    """Compare flight prices to several destinations, find deals, and suggest similar cities.

    Use this when the user wants to compare places, asks which destination is cheaper,
    asks whether a fare is a good price or a deal, wants to know the cheapest time to
    go, or asks for somewhere "like" a city (for example "like Amsterdam but cheaper").
    For a single known route and date, use search_flights instead.

    It samples the cheapest one-way fare on several weekly departure dates per
    destination, compares each date to the route's baseline (sampled dates plus earlier
    saved searches), flags dates at least 15% below baseline as deals, and compares
    destinations with a similar feel (shared traits like canals, nightlife, museums).

    Args:
        origin: 3-letter IATA airport code, e.g. "JFK".
        destinations: 1 to 4 destinations, as IATA codes or city names, e.g. ["AMS", "Berlin"].
        start_date: First departure date, YYYY-MM-DD. Defaults to two weeks from today.
        num_dates: Weekly departure dates to sample per destination (2 to 6, default 4).
        include_similar: Also search up to 2 destinations with a similar feel to the first
            destination and compare their prices (default true).

    Returns:
        A JSON object: {status: "ok"|"partial"|"error", data_mode, origin, currency,
        window: [dates], destinations: [{iata, city, samples: [{date, price, airline,
        stops}], failed_dates, cheapest_date, cheapest_price, median_price,
        baseline_price, baseline_observations, baseline_source, deals: [{date, price,
        pct_below_baseline}], verdict: "deal"|"typical"|"insufficient_data"}],
        ranking: [iata...] cheapest typical fare first, similar: [{report, similar_to,
        shared_traits, similarity, cheaper_than_anchor_pct}], notes: [...], error}.
        data_mode "test" means sandbox fares, so deals are illustrative.
    """
    origin = origin.upper().strip()
    if len(origin) != 3 or not origin.isalpha():
        return _error(origin, "origin must be a 3-letter IATA airport code")
    if not destinations:
        return _error(origin, "provide at least one destination")

    dests, unknown = [], []
    for d in destinations:
        code = _resolve(d)
        (dests if code else unknown).append(code or d)
    dests = list(dict.fromkeys(dests))
    if unknown:
        return _error(origin, "could not resolve destination(s): " + ", ".join(unknown)
                      + ". Use 3-letter IATA codes.")
    if len(dests) > MAX_DESTINATIONS:
        return _error(origin, f"compare at most {MAX_DESTINATIONS} destinations per report")
    if origin in dests:
        return _error(origin, "origin cannot also be a destination")

    today = datetime.now().date()
    try:
        first = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else today + timedelta(days=14)
    except ValueError:
        return _error(origin, "start_date must be in YYYY-MM-DD format")
    if first < today:
        return _error(origin, f"{first.isoformat()} is in the past; today is {today.isoformat()}")

    # Pick similar destinations for the first profiled destination.
    similar_meta: list[tuple[str, str, float, list[str]]] = []
    if include_similar:
        for anchor in dests:
            if anchor in PROFILES:
                for code, score, shared in similar_destinations(anchor, set(dests) | {origin}, limit=2):
                    similar_meta.append((code, anchor, score, shared))
                break

    all_codes = dests + [m[0] for m in similar_meta]
    num_dates = max(2, min(int(num_dates), 6, MAX_SEARCHES // len(all_codes)))
    window = [(first + timedelta(days=7 * i)).isoformat() for i in range(num_dates)]

    jobs = [(c, d) for c in all_codes for d in window]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outputs = list(pool.map(lambda j: (j[0], _sample_one(origin, j[0], j[1])), jobs))
    by_dest: dict[str, list] = {c: [] for c in all_codes}
    for code, res in outputs:
        by_dest[code].append(res)

    history = _load_history()
    today_iso = today.isoformat()
    reports, all_new, currencies = {}, [], []
    for code in all_codes:
        rep, new, cur = _build_report(origin, code, by_dest[code], history, today_iso)
        reports[code] = rep
        all_new += new
        if cur:
            currencies.append(cur)
    saved = _save_history(_merge(history, all_new)) if all_new else True

    notes = []
    if _data_mode() == "test":
        notes.append("Sandbox data: fares are synthetic, so deals are illustrative, not real savings.")
    notes.append("No fare-history feed exists in the flight API. Baselines come from the sampled "
                 "dates plus earlier saved searches, and they sharpen as more searches are saved.")
    if not saved:
        notes.append("Could not save price history on this run.")
    if len(set(currencies)) > 1:
        notes.append("Mixed currencies were returned; compare prices within one currency only.")

    requested = [reports[c] for c in dests]
    ranked = sorted((r for r in requested if r.median_price is not None), key=lambda r: r.median_price)
    anchor_median = None
    if similar_meta:
        anchor_median = reports[similar_meta[0][1]].median_price

    similar = []
    for code, anchor, score, shared in similar_meta:
        rep = reports[code]
        pct = None
        if anchor_median and rep.median_price is not None:
            pct = round((1 - rep.median_price / anchor_median) * 100, 1)
        similar.append(SimilarDestination(report=rep, similar_to=anchor, shared_traits=shared,
                                          similarity=score, cheaper_than_anchor_pct=pct))

    got_any = any(r.samples for r in reports.values())
    all_ok = all(r.samples and not r.failed_dates for r in reports.values())
    status = "error" if not got_any else ("ok" if all_ok else "partial")
    error = None
    if not got_any:
        sample_err = next((e for res in by_dest.values() for (_, _, e) in res if e), "no flights found")
        error = f"No fares could be retrieved: {sample_err}"
    return ComparisonReport(
        status=status, data_mode=_data_mode(), origin=origin,
        currency=currencies[0] if currencies else None, window=window,
        destinations=requested, ranking=[r.iata for r in ranked],
        similar=similar, notes=notes, error=error,
    ).model_dump_json()


if __name__ == "__main__":
    # Quick manual test:  python -m tools.destinations
    print(compare_destinations.invoke({"origin": "JFK", "destinations": ["AMS"]}))
