import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from anywhere

import json, os, tempfile
from datetime import date, timedelta
from pathlib import Path
os.environ["DUFFEL_API_KEY"] = "duffel_test_x"
from tools import destinations as dc
from tools.flights import Flight

dc.HISTORY_FILE = Path(tempfile.mkdtemp()) / "h.json"

PRICES = {"AMS": [400, 410, 300, 420, 405, 415], "BER": [300, 310, 305, 295, 300, 310],
          "PRG": [250, 260, 255, 250, 245, 255]}
def fake(origin, dest, day):
    if dest == "XXX": raise RuntimeError("boom")
    idx = ((date.fromisoformat(day) - (date.today()+timedelta(days=14))).days)//7
    return [Flight(offer_id="o", airline="Duffel Airways", flight_number="ZZ1", departs=day+"T08:00:00",
                   arrives=day+"T20:00:00", duration="PT7H", stops=0,
                   price=float(PRICES[dest][idx]), currency="USD")]
dc._fetch_flights = fake

def run(**kw): return json.loads(dc.compare_destinations.invoke(kw))

r = run(origin="JFK", destinations=["Amsterdam"], num_dates=6)
print(r["status"], r["ranking"], r["window"][:2])
ams = r["destinations"][0]
assert ams["city"] == "Amsterdam" and ams["verdict"] == "deal" and ams["deals"][0]["price"] == 300, ams
assert ams["baseline_source"] == "sampled_calendar"
assert r["similar"] and r["similar"][0]["similar_to"] == "AMS"
codes = [s["report"]["iata"] for s in r["similar"]]
print("similar:", codes, [s["cheaper_than_anchor_pct"] for s in r["similar"]])
assert "BER" in codes
assert any("Sandbox" in n for n in r["notes"])
assert dc.HISTORY_FILE.exists()

# second run reuses stored history
r2 = run(origin="JFK", destinations=["AMS"], include_similar=False, num_dates=6)
print(r2["destinations"][0]["baseline_observations"], r2["destinations"][0]["baseline_source"])

# multi-destination ranking
r3 = run(origin="JFK", destinations=["AMS","BER","PRG"], include_similar=False, num_dates=4)
print(r3["ranking"]); assert r3["ranking"][0] == "PRG"

# errors as data
for kw in [dict(origin="JF", destinations=["AMS"]), dict(origin="JFK", destinations=["Atlantis"]),
           dict(origin="JFK", destinations=["AMS"], start_date="2020-01-01"),
           dict(origin="JFK", destinations=["AMS"], start_date="12/20"),
           dict(origin="JFK", destinations=["JFK"]), dict(origin="JFK", destinations=[])]:
    e = run(**kw); assert e["status"] == "error" and e["error"], kw
# all fail
r4 = run(origin="JFK", destinations=["XXX"], include_similar=False)
assert r4["status"] == "error" and "boom" in r4["error"], r4
# similarity symmetry
assert dc.similar_destinations("AMS", set(), 3)[0][0] in ("BER","CPH","HAM")
assert "AMS" in [c for c,_,_ in dc.similar_destinations("BER", set(), 4)]
# search cap
calls = []
dc._fetch_flights = lambda o,d,day: (calls.append(1), fake(o,d,day) if d in PRICES else [])[1]
run(origin="JFK", destinations=["AMS","BER","PRG","CPH"], num_dates=6)
assert len(calls) <= dc.MAX_SEARCHES, len(calls)
print("ALL PASS, calls:", len(calls))
