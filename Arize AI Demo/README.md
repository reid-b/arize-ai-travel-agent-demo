# Sojourns by Arize AI

A travel-planning agent built with LangGraph, served by FastAPI with a branded chat UI, and traced end to end with [Arize Phoenix](https://github.com/Arize-ai/phoenix). 

| Tool | Source | What it does |
|---|---|---|
| `web_search` | DuckDuckGo via `ddgs` (auto, duckduckgo, bing), then the Wikivoyage API | Travel ideas and tips |
| `compare_destinations` | Duffel, sampled by date | Typical fare, deals (at least 15% under baseline) and similar cities |
| `search_flights` | Duffel | Up to 5 one-way offers, cheapest first |
| `search_car_rentals` | OctoTrip rental search | Up to 6 offers, cheapest first |

Every tool returns structured JSON. Failures come back as data, so the agent can explain them or retry.

## Prerequisites

- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [Duffel](https://duffel.com) API key for flights and destination comparison. A `duffel_test_...` key returns synthetic sandbox fares, and the app labels them as test data.
- Python 3.11+ (to run locally) or Docker (to run in containers)

## Quick start with Docker

```bash
cp .env.example .env        # then add OPENAI_API_KEY and DUFFEL_API_KEY
docker compose up --build
```

- App: http://localhost:8000
- Phoenix (traces): http://localhost:6006

Compose starts Phoenix and the app together, and the app waits for Phoenix before it starts so tracing is on. Fare history is kept in a Docker volume.

To run only the app image (without Phoenix, so no traces):

```bash
docker build -t sojourns .
docker run --rm -p 8000:8000 --env-file .env -e PHOENIX_TRACING=0 sojourns
```

## Quick start without Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then add OPENAI_API_KEY and DUFFEL_API_KEY
```

Start Phoenix in a separate environment (it pins its own dependencies):

```bash
python3 -m venv .venv-phoenix
.venv-phoenix/bin/pip install arize-phoenix
.venv-phoenix/bin/phoenix serve        # UI at http://localhost:6006
```

Then start the app in another terminal:

```bash
uvicorn api:app --reload
```

Open http://localhost:8000. If Phoenix isn't running, the app still works and prints one message saying tracing is off. Start Phoenix and restart the app to turn tracing on.

Poetry also works: `poetry install` then `poetry run uvicorn api:app --reload`.

On macOS you can double-click `Sojourns by Arize AI DEMO.command`. It creates a virtual environment, installs the dependencies and Phoenix, starts both, and opens the app.

## Configuration

Set these in `.env` (see `.env.example`).

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Yes | The agent's LLM |
| `DUFFEL_API_KEY` | For flights and comparison | Duffel API access |
| `PHOENIX_PROJECT_NAME` | No | Phoenix project name (default `sojourns`) |
| `PHOENIX_COLLECTOR_ENDPOINT` | No | Phoenix URL (default `http://localhost:6006`) |
| `PHOENIX_API_KEY` | No | Only if your Phoenix has auth enabled |
| `PHOENIX_TRACING` | No | Set to `0` to turn tracing off |
| `SOJOURNS_PRICE_HISTORY` | No | Where fare observations are saved (default `data/price_history.json`) |

## Try it

The **Demo prompts** menu in the app header has twelve ready-made prompts. For example:

- "Compare Vegas to Atlantic City" draws price charts from `compare_destinations`.
- "Find flights and car rentals for Las Vegas" calls two tools in one turn.
- "I want a warm beach resort trip in January. Recommendations?" uses `web_search`.

You can also call the API directly:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find flights to Las Vegas", "session_id": "demo-1"}'
```

`POST /chat` takes `message`, optional `history` (prior turns, oldest first) and optional `session_id`, which groups a conversation's traces in Phoenix. `GET /health` is the health check.

## Observability

`tracing.py` registers Phoenix as the OpenTelemetry destination and turns on the OpenInference LangChain instrumentor, so each `/chat` request becomes a trace: the LangGraph run, each LLM call and each tool call. No changes to the agent code are needed. Open Phoenix, go to the `sojourns` project, and follow a request through its spans.

## Evaluation

`eval_data/` holds two CSVs for a user-frustration evaluator in the Phoenix UI:

- `frustration_eval_dataset_from_traces.csv`: 16 follow-up turns taken from a real session's traces.
- `frustration_eval_dataset.csv`: 22 synthetic examples.

Upload one as a dataset in Phoenix and map `user_prompt`, `assistant_answer` and `follow_up` to the input and `label` to the output. Then attach an LLM evaluator that reads the three messages and returns `frustrated` or `not_frustrated`, and run it as an experiment.

## Tests

The tests run offline, with the network calls stubbed out:

```bash
python tests/test_web_search.py
python tests/test_destination_compare.py
```

## Project structure

```
├── api.py                  # FastAPI server: /chat, /health, serves the UI
├── agent.py                # LangGraph loop and system prompt
├── tracing.py              # Phoenix / OpenInference setup
├── tools/                  # the agent's tools
│   ├── flights.py          #   search_flights (Duffel)
│   ├── cars.py             #   search_car_rentals (OctoTrip)
│   ├── destinations.py     #   compare_destinations (deals, similar cities)
│   └── web.py              #   web_search (multi-engine + Wikivoyage fallback)
├── static/index.html       # branded chat UI with charts
├── tests/                  # offline tests
├── eval_data/              # datasets for the frustration evaluator
├── docs/                   # DESIGN.md and brand guidelines
├── assets/                 # app icon files
├── data/                   # saved fare history (git-ignored)
├── Dockerfile
├── docker-compose.yml      # app + Phoenix
├── docker/entrypoint.sh    # waits for Phoenix before starting
├── requirements.txt
└── pyproject.toml
```

See `docs/DESIGN.md` for the design decisions.

## Notes and limits

- Duffel sandbox fares are synthetic. Duffel has no historical-fare endpoint, so "history" means a sampled weekly price calendar plus the observations saved in `data/price_history.json` (kept for 90 days).
- Web search never supplies fares or prices. Those come only from the flight and rental tools.
