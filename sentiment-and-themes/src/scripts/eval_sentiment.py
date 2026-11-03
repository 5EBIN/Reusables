"""Scores the configured LLM provider (LLM_PROVIDER and its settings in .env) on the labelled sentiment set and prints accuracy per language and per
confidence bucket. Run it before switching model or provider, and again after changing the prompt:

    python scripts/eval_sentiment.py            # batches of 50, as the app does
    python scripts/eval_sentiment.py --batch 1  # the label should not depend on batch size: compare the two runs
    python scripts/eval_sentiment.py --set survey  # the second set: survey-style comments across sectors

A model's own confidence is not calibrated, so check that accuracy rises from the lowest bucket to the highest before trusting the 0.6 cut-off."""
import argparse
import asyncio
import json
import os
import re
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"
for line in ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []:
    m = re.match(r"^([A-Z_][A-Z0-9_]*)=([^#\n]*)", line)
    if m:
        os.environ.setdefault(m.group(1), m.group(2).strip())

from app.app.container import build_container                                  # noqa: E402
from app.core.sentiment import MAX_BATCH, from_model, golden_report, golden_rows   # noqa: E402


async def main(batch: int, which: str) -> None:
    llm = build_container().llm
    rows = golden_rows(which)
    scored = []
    for i in range(0, len(rows), batch):
        texts = [r["text"] for r in rows[i:i + batch]]
        scored += from_model(texts, await llm.classify_sentiment(texts))
    it = iter(scored)
    report = golden_report(lambda texts: [next(it) for _ in texts], batch, which)
    print(json.dumps({"provider": type(llm).__name__, "model": getattr(llm, "model", None), "batch": batch, "set": which, **report}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=MAX_BATCH)
    ap.add_argument("--set", choices=["core", "survey"], default="core", help="core: the original examples; survey: survey-style comments across sectors")
    a = ap.parse_args()
    asyncio.run(main(a.batch, a.set))
