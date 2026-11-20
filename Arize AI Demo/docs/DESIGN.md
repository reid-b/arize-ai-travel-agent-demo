# Design notes: flight search extension

This document covers the `search_flights` tool added to the LangGraph agent
(`tools/flights.py`), the decisions behind it, and what it deliberately does not do.

## What the extension is

A LangChain tool, `search_flights(origin, destination, date)`, that queries the Duffel
offers API and returns a structured JSON result. It is registered in `tools/__init__.py`, so the
existing graph picks it up with no graph changes:

    tools/__init__.py  ->  model.bind_tools(tools)  ->  llm_call  ->  tool_node  ->  llm_call

## How it meets the requirements

| Requirement | How |
|---|---|
| Integrates into the agent workflow | One entry in the `tools` list. `bind_tools` advertises its schema to the model; `tool_node` dispatches by name via `tools_by_name`. The graph is unchanged. |
| Invoked by the agent when relevant | The model chooses tools from their name, docstring and argument schema, plus one line in the system prompt that routes flight questions to `search_flights` and keeps web search for general travel info. The docstring says "use this for flight options, times or prices". |
| Returns structured output | The tool returns a JSON document with a fixed schema (`FlightSearchResult` / `Flight`, Pydantic models). Fields are listed below. |

## Output schema

    {
      "status": "ok" | "no_results" | "error",
      "source": "duffel",
      "data_mode": "test" | "live" | "unknown",
      "origin": "JFK", "destination": "LAX", "date": "2026-12-20",
      "flights": [{
        "offer_id", "airline", "flight_number",
        "departs", "arrives",      // ISO 8601 local times
        "duration",                // ISO 8601 duration, e.g. "PT5H50M"
        "stops", "price", "currency"
      }],
      "error": null | "message"
    }

## Design decisions

1. **A separate module, not inline in `agent.py`.** Tools are the part of an agent that
   changes most. Keeping each in its own file keeps `agent.py` about orchestration only
   and makes the tool testable without importing the model.

2. **JSON string as the tool return type.** LangGraph's `ToolMessage` content must be a
   string, so the tool serializes a Pydantic model with `model_dump_json()`. That gives
   a stable, typed contract for the model, for tests and for any future UI, without
   changing `tool_node`. A free-text summary was the first draft; it was rejected
   because the model could not reliably distinguish "no flights" from "search failed".

3. **Errors are data, not exceptions.** Bad input, a missing key, a past date, a Duffel
   4xx/5xx or a network failure all come back as `status: "error"` with a message. The
   model reads it and can correct the input (for example a past date) or explain the
   problem. An uncaught exception would end the whole request with a 500. `tool_node`
   also catches anything unexpected as a last line of defense.

4. **Validate before calling the network.** IATA codes, date format and "not in the
   past" are checked locally. It is cheap, it avoids spending API quota on predictable
   failures, and the error messages are written for the model to act on.

5. **The model is told today's date.** The system prompt includes the current date and
   a rule to use the next upcoming occurrence of a date given without a year. Without
   it, "December 20" can resolve to a past year, which the API rejects.

6. **Duffel as the data source.** Duffel has a free self-serve test mode and well-documented
   request and response formats. The trade-off: test mode returns sandbox data from a
   fake airline, not live fares.

7. **`data_mode` is part of the output.** The tool reports `test` or `live` (from the
   token prefix) so the agent can tell the user when fares are sandbox data instead of
   presenting them as real.

8. **Results capped at the 5 cheapest.** Duffel can return dozens of offers. Capping
   keeps tool output small for the model's context and gives it a short list to
   summarize. The cap is the `MAX_RESULTS` constant.

9. **Web search stays, with a boundary.** DuckDuckGo snippets are not a reliable source
   of fares, but they are fine for soft questions (neighbourhoods, baggage rules). The
   prompt says to use web search for general information only, never for fares.

10. **One-way, one adult, economy.** The smallest useful scope. The `_fetch_flights`
    helper already takes `adults` and `cabin`, so extending the tool signature is a
    small change.

## Testing

The tests in `tests/` run offline (no network, no key) with a mocked HTTP layer. It
covers the success path and ordering, the exact output fields, no results, input
validation, an HTTP error, and a missing key. Run them with `python tests/<file>.py`.

Not yet covered: an automated check that the model actually calls the tool for a flight
question. That needs a live model call and is best done as an eval.

## Known limitations and next steps

- One-way trips only; no round trip, multiple passengers or cabin selection yet.
- Test-mode data is synthetic. Moving to live fares needs a Duffel live account.
- No retries or caching; each call hits the API.
- Add tracing and evals (for example Arize Phoenix) to measure how often the agent
  picks the right tool and how it handles error results.
- The UI shows the agent's text reply. Since the tool output is structured, the API
  could pass `flights` through so the UI renders flight cards.

## Observability with Arize Phoenix

Agent runs are traced with [Arize Phoenix](https://github.com/Arize-ai/phoenix) through
OpenTelemetry and the OpenInference LangChain instrumentor, which also covers LangGraph.
Each run appears as a trace with its LLM calls, tool calls (including `search_flights`
and its JSON output) and graph steps.

Decisions:

1. **Instrument, don't hand-write spans.** `tracing.py` calls `phoenix.otel.register(
   auto_instrument=True)` once at startup. No agent or tool code changes, and new tools
   are traced automatically.
2. **Tracing can never break the app.** If the packages or the Phoenix server are
   missing, `setup_tracing()` logs a warning and the agent runs untraced.
3. **Register before the agent is built** (`api.py`), so LangChain is instrumented
   before the first run.
4. **Conversations are grouped.** The UI sends a per-tab `session_id`, passed to the
   agent as run metadata, so a multi-turn chat shows up as one session in Phoenix.
5. **Phoenix runs in its own virtual environment** (`.venv-phoenix`), started and
   stopped by the launcher, so its many dependencies cannot conflict with the app's
   pinned versions.
6. **Local by default, remote by configuration.** With nothing set, traces go to local
   Phoenix on port 6006. Set `PHOENIX_COLLECTOR_ENDPOINT` (and `PHOENIX_API_KEY` if the
   deployment requires one) to send them elsewhere. `PHOENIX_TRACING=0` turns it off.


## Car rental search (second data-source tool)

`tools/cars.py` adds `search_car_rentals(location, pickup_date, dropoff_date,
dropoff_location, driver_age, currency)`. It follows the same pattern as the flight
tool: its own module, a Pydantic output schema (`CarRentalResult` / `CarOffer`) returned
as JSON, and errors reported as data.

Decisions:

1. **A different provider on purpose.** Duffel has no car rental product, and the
   hotel product (Stays) turned out to be gated. Most car rental APIs (Booking.com,
   Kayak, Expedia) are partner-only. OctoTrip's hosted rental search is free and needs
   no key, so it is the one self-serve option that works for a demo. It also shows the
   agent mixing tools from different sources behind the same output contract.
2. **Call the MCP server over plain HTTP.** The service is an MCP server, but its
   hosted endpoint is stateless Streamable HTTP with JSON-RPC, so two `requests.post`
   calls (`initialize`, then `tools/call`) are enough. That avoids adding an MCP client
   dependency and keeps the tool a normal LangChain tool with our own schema.
3. **Normalize the third-party output.** The agent never sees the provider's raw
   payload. The tool maps it to a stable schema, sorts by total price and caps the list
   at six offers.
4. **Parse defensively (and learn from live responses).** The live service wraps its answer as JSON text inside a `result` field (and uses a singular `suggestion` key); `_unwrap` peels that off. Beyond that, the provider groups offers by car category and its exact
   nesting is not documented, so the tool collects offers wherever they appear. If the
   response matches nothing known, the tool returns `status: "error"` with a short
   preview instead of an empty or invented result, which makes a format change easy to
   spot in Phoenix.
5. **Validate before the network call.** The provider is limited to one request per
   second, so dates, age and currency are checked locally.
6. **Say what the data is.** The provider's booking links may carry affiliate
   attribution (it states results are ranked by price, not payout). The tool passes that
   in `note`, and the prompt tells the agent to mention it and to say the tool cannot book.

Known limits: search only, no booking; two offers per car category (a provider limit);
rate limit of one request per second. The response parser was written from the
provider's README and tested against mocked responses; it has not been run against the
live service from the build environment.


## Destination comparison (third tool)

`tools/destinations.py` adds `compare_destinations`, which answers "which place is cheaper", "is this a deal" and "somewhere like Amsterdam but cheaper".

- **Reuses the flight tool.** It calls `tools.flights._fetch_flights` for each destination and date, so there is one Duffel integration and one set of failure modes.
- **Price calendar instead of a history feed.** Duffel has no historical-fares endpoint. The tool samples the cheapest fare on several weekly departure dates (default 4, max 6) and saves every observation to `data/price_history.json` (90-day window, git-ignored). The baseline is the median of saved plus sampled observations, so it gets better with use. The report states which source the baseline came from (`sampled_calendar` or `stored_history`) and never calls it official history.
- **Deal rule.** A date is a deal when its fare is at least 15% below the route baseline, and needs at least 4 observations. Otherwise the verdict is `insufficient_data`, not a guess.
- **Similar experiences.** A small curated table of 18 cities with trait tags (canals, nightlife, museums, budget...). Similarity is Jaccard overlap of traits, so Amsterdam maps to Berlin and Copenhagen. The tool searches up to 2 similar cities for the first profiled destination and reports `cheaper_than_anchor_pct` by median fare. The table is data, easy to extend, and the traits are shown so the agent can explain the match.
- **Bounded cost.** At most 24 Duffel searches per report (dates shrink as destinations grow), run 5 at a time. Failed dates are listed and the report becomes `partial`.
- **Same conventions.** Fixed Pydantic schema, errors returned as data, `data_mode` carried through so sandbox prices are labeled as illustrative.
- **Limits.** Sandbox fares are synthetic, one-way only, and the profile table is hand-curated. A real fare-history source or live token would improve deal accuracy.

### Charts for the comparison report

`/chat` also returns `reports`, the raw `compare_destinations` JSON from that turn (found by matching tool call ids, so the agent's prose and the charts come from the same data). The UI draws two inline SVG charts from it with no chart library: a price calendar (one line per city, dashed baseline, pink rings on deals) and a typical-fare bar chart that includes the similar cities and how much cheaper they are. Colors use the brand accent tokens with dark-mode variants, each chart has an `aria-label`, and sandbox data is labeled under the chart.


## Resilient web search

The first web search tool (DuckDuckGo through LangChain) failed often enough to break a demo, usually from rate limiting, and its errors reached the model as vague text. `tools/web.py` replaces it. It tries up to three search backends in turn, then falls back to Wikivoyage's public API for destination guides. It returns the same fixed-schema JSON as the other tools: status, which source answered, results, and an `attempts` list with the reason each source failed. Errors are returned as data, the agent is told to say plainly when search fails and to label any answer from general knowledge, and every failure is also printed to the Terminal. Fares still never come from web search.
