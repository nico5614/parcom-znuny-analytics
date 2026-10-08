"""Generate isolated browser-test DTO fixtures using the production Python adapters."""
import argparse
from datetime import timedelta
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parcom_analytics.live_cache import LiveCache
from parcom_analytics.periods import PRESETS, TimeRange, now
from parcom_analytics.web.dto import TYPES, analysis_dto, agents_dto, overview, period_dto, ticket_details
from parcom_analytics.web.settings import Settings
from parcom_analytics.web.validation import validation_batch

parser = argparse.ArgumentParser()
parser.add_argument('--screenshots', action='store_true')
args = parser.parse_args()
if args.screenshots:
    # Only this isolated fixture process: never expose real identity seeds in documentation.
    from parcom_analytics import agents
    keys = [key for key in agents.SEED_AGENTS if key != '1'] + ['99']
    for index, key in enumerate(keys, 1):
        agents.SEED_AGENTS[key] = ('', f'Beispieltechniker {index:02}', f'T{index:02}')

with tempfile.TemporaryDirectory(prefix="parcom-browser-fixtures-") as directory:
    cache = LiveCache(Path(directory))
    batch = validation_batch()
    if args.screenshots:
        batch.history_loaded = True  # Synthetic closed/response events are supplied by this fixture.
    cache.update(batch)
    settings = Settings(Path(directory))
    end = now()
    data = {"overview": overview(cache, settings), "analyses": {str(kpi): {kind or "all": analysis_dto(cache, kpi, kind) for kind in (None, *TYPES)} for kpi in range(1, 8)},
            "agents": agents_dto(cache, settings), "tickets": {str(value): ticket_details(cache, str(value)) for value in range(102, 120)},
            "periods": {preset: period_dto(TimeRange.preset(preset), preset) for preset in PRESETS},
            "custom": period_dto(TimeRange(end-timedelta(days=2), end)), "capturedAt": cache.batch.captured_at}
    target = ROOT / "frontend" / ".validation" / ("docs-fixtures.json" if args.screenshots else "fixtures.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"Synthetic browser fixtures: {target}")
