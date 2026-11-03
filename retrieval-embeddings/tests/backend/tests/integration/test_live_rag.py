"""How often the real model's "Ask your survey" drafts pass the verifier (quotations verbatim, no digits, only retrieved ids). Costs a few cents; never runs unless EVAL_LIVE=1:

    EVAL_LIVE=1 python -m pytest tests/integration/test_live_rag.py -m live -s

Five questions (English and Arabic) over five short answers each, three drafts per question. The verifier is not loosened to make this pass: a draft it rejects counts as a miss."""
from collections import Counter

import pytest

from app.app.container import build_container
from app.core import rag
from tests.integration.test_live_model import env_from_file

pytestmark = pytest.mark.live
MIN_VERIFIED = 0.85
SCENARIOS = [
    ("What do residents say about parking?", ["Visitor parking is a nightmare, my guests circle for twenty minutes", "There are not enough spaces on weekends and cars block the exit",
                                              "Parking fees keep going up every year", "I love the pool but the parking is terrible", "Guests get fined even with a permit"]),
    ("ماذا يقول السكان عن الصيانة؟", ["الصيانة بطيئة جداً وننتظر أسبوعين لإصلاح المصعد", "فريق الصيانة متعاون لكن الطلبات تتأخر", "تم إصلاح التسريب في نفس اليوم والحمد لله",
                                     "لا أحد يرد على طلبات الصيانة في عطلة نهاية الأسبوع", "المصعد معطل منذ شهر"]),
    ("How do people feel about the staff?", ["The front desk team is so helpful and kind", "Reception staff were rude to my mother", "Security is friendly and always smiling",
                                             "Staff changes too often so nobody knows our names", "Great service from the concierge"]),
    ("What are the main complaints about noise?", ["Construction drilling starts at 7am every day", "The neighbours above us party until 3am on weekdays",
                                                   "Noise from the gym early morning wakes the whole floor", "It is quiet at night which I like", "Delivery trucks are loud at the loading bay"]),
    ("ما هي الشكاوى المتعلقة بالأسعار؟", ["الإيجار ارتفع بشكل كبير هذه السنة", "رسوم الخدمة غالية مقارنة بالمبنى المجاور", "الأسعار مناسبة لكن الرسوم الإضافية مزعجة",
                                          "لم أفهم لماذا زادت رسوم المواقف", "نريد خطة دفع شهرية بدل الدفع السنوي"]),
]


async def test_the_real_model_drafts_answers_the_verifier_accepts():
    env = env_from_file()
    if not env.get("LLM_API_KEY") or env.get("LLM_PROVIDER") != "openai_compat":
        pytest.skip("backend/.env has no OpenRouter configuration")
    llm = build_container({**env, "APP_ENV": "test", "AUTH_PROVIDER": "fake"}).llm
    outcome: Counter = Counter()
    for question, texts in SCENARIOS:
        evidence = [{"id": f"e{i + 1}", "text": t} for i, t in enumerate(texts)]
        shown = {e["id"]: e["text"] for e in evidence}
        for _ in range(3):
            try:
                draft = await llm.answer_from_evidence(question, evidence, {})
                if draft:
                    rag.verify_answer(draft, shown)
                outcome["verified" if draft else "empty"] += 1
            except rag.AnswerRejected as e:
                outcome[f"rejected: {e}"] += 1
            except Exception as e:                                                       # an outage counts as a miss
                outcome[f"error: {type(e).__name__}"] += 1
    total = sum(outcome.values())
    print(f"\n=== RAG DRAFTS === {dict(outcome)}")
    assert outcome["verified"] / total >= MIN_VERIFIED
