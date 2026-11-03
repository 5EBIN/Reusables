"""Canned LLM for tests: plans keyed by phrases; never emits SQL. Like the real adapters it reports what each answer 'cost' (`call_usage`, settable per test), so the
usage, cost and cap code runs the same with the fake as with a provider."""
import functools
import uuid
from typing import Any

from app.adapters.llm_tasks import CallInfo, LLMTasks

TASK_OF = {"plan": "plan", "classify": "classify", "draft_survey": "survey", "propose_themes": "themes", "narrate": "narrate", "interview_next": "interview",
           "extract_facts": "facts", "propose_benchmarks": "benchmarks", "propose_cluster_labels": "cluster_labels", "answer_from_evidence": "rag", "classify_sentiment": "sentiment"}


def _reporting(task: str, fn):
    @functools.wraps(fn)
    async def inner(self, *a, **k):
        out = await fn(self, *a, **k)
        LLMTasks._record(CallInfo(model="FakeLLM", task=task, generation_id=f"fake-{uuid.uuid4().hex[:8]}", usage=dict(self.call_usage)), out, False)
        return out
    return inner


class FakeLLM:
    def __init__(self):
        self.plans: dict[str, dict] = {}
        self.calls: list[dict] = []
        self.draft: dict | list | None = None
        self.themes: list[dict] = []
        self.narratives: dict[str, list[dict]] = {}
        self.usage = 0
        self.call_usage: dict[str, Any] = {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50, "cost": 0.0}      # what every answer reports
        self.interview: dict | None = None
        self.facts: dict[str, list[dict]] = {}
        self.benchmark_rows: dict[str, list[dict]] = {}
        self.rag_answer: list[dict] | Any = None          # canned sentences [{text, evidence_ids}] (or a callable(question, evidence, labels)->sentences); default = none (nothing supported)
        self.sentiment_results: list[dict] | Any = None   # canned [{label, confidence}] (or a callable(texts)->results); default = the word list, so tests are deterministic
        self.classes: dict[str, str] = {}                 # tagging: a phrase in an answer -> the theme id the model picks for it (default "other")
        self.cluster_labels: list[dict] | Any = None      # canned proposals (or a callable(clusters)->proposals); default = none (clusters stay unlabelled)

    async def plan(self, text: str, catalog: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"text": text, "catalog_keys": sorted(catalog), "catalog": catalog})
        for phrase, plan in self.plans.items():
            if phrase.lower() in text.lower():
                return plan
        return {"outcome": "CLARIFY", "clarify_question": "What do you want to know?"}

    async def classify(self, texts: list[str], theme_ids: list[str]) -> list[str]:
        self.calls.append({"classify": list(texts), "theme_ids": list(theme_ids)})
        return [next((t for phrase, t in self.classes.items() if phrase.lower() in x.lower()), "other") for x in texts]

    async def draft_survey(self, brief: str, language: str, goal: str) -> dict[str, Any]:
        if isinstance(self.draft, list):
            return self.draft.pop(0)
        return self.draft or {"pages": []}

    async def propose_themes(self, texts: list[str], max_themes: int) -> list[dict[str, Any]]:
        self.calls.append({"propose_themes": len(texts), "texts": list(texts)})
        return self.themes[:max_themes]

    async def narrate(self, kind: str, computed: dict[str, float], labels: dict[str, str]) -> list[dict[str, Any]]:
        self.calls.append({"narrate": kind, "refs": sorted(computed)})
        return self.narratives.get(kind, [])

    async def interview_next(self, objective: str, answer: str, language: str) -> dict[str, Any]:
        self.calls.append({"interview_next": objective})
        return self.interview or {"question": "Could you tell me more about that?", "looks_covered": False}

    async def extract_facts(self, page_text: str, question: str) -> list[dict[str, Any]]:
        self.calls.append({"extract_facts": question})
        return [f for k, v in self.facts.items() if k in page_text for f in v]

    async def propose_benchmarks(self, evidence_text: str, dimensions: list[str]) -> list[dict[str, Any]]:
        self.calls.append({"propose_benchmarks": sorted(dimensions)})
        return [r for k, v in self.benchmark_rows.items() if k in evidence_text for r in v]

    async def propose_cluster_labels(self, clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.calls.append({"propose_cluster_labels": [c["cluster_no"] for c in clusters], "clusters": clusters})
        if callable(self.cluster_labels):
            return self.cluster_labels(clusters)
        return list(self.cluster_labels or [])

    async def answer_from_evidence(self, question: str, evidence: list[dict[str, str]], labels: dict[str, str]) -> list[dict[str, Any]]:
        self.calls.append({"answer_from_evidence": question, "evidence": evidence, "labels": labels})
        if callable(self.rag_answer):
            return self.rag_answer(question, evidence, labels)
        return list(self.rag_answer or [])

    async def classify_sentiment(self, texts: list[str], hint: str | None = None) -> list[dict[str, Any]]:
        self.calls.append({"classify_sentiment": len(texts), "hint": hint})
        if callable(self.sentiment_results):
            return self.sentiment_results(texts)
        if self.sentiment_results is not None:
            return self.sentiment_results
        from app.core.sentiment import NAMES, from_lexicon
        return [{"label": NAMES[s.label], "confidence": s.confidence} for s in from_lexicon(texts)]


for _name, _task in TASK_OF.items():
    setattr(FakeLLM, _name, _reporting(_task, getattr(FakeLLM, _name)))
