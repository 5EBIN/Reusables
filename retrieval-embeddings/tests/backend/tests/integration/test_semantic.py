import json
import uuid
from types import SimpleNamespace as NS

import pytest

from app.adapters.llm_anthropic import AnthropicLLM
from app.db import tenant_tx

DEF = {"pages": [{"elements": [{"type": "rating", "name": "nps", "rateMin": 0, "rateMax": 10}, {"type": "comment", "name": "why"}]}]}
NEG = ["terrible", "awful", "زفت", "سيء", "terrible!!", "awful!!", "زفت جدا", "سيء جدا"]
POS = ["excellent", "great", "ممتاز", "رائع", "excellent!!", "great!!", "ممتاز جدا", "رائع جدا"]
OTHER = ["parking garage"]
SYN = {**{w: "NEGATIVE" for w in ("terrible", "awful", "زفت", "سيء")}, **{w: "POSITIVE" for w in ("excellent", "great", "ممتاز", "رائع")}}
THEMES = [{"key": "complaints", "label": {"en": "Complaints", "ar": "شكاوى"}, "definition": "d", "keywords": ["terrible", "awful", "زفت", "سيء"]},
          {"key": "praise", "label": {"en": "Praise"}, "definition": "d", "keywords": ["excellent", "great", "ممتاز", "رائع"]}]


@pytest.fixture(autouse=True)
def _syn(app):
    e = app.state.container.embedder
    for w, c in SYN.items():
        e.add_synonym(w, c)
    llm = app.state.container.llm
    saved = llm.cluster_labels
    yield
    llm.cluster_labels = saved


async def seed(make_user, client, texts=NEG + POS + OTHER):
    u = make_user(); org = await u.create_org(); h = u.headers(org)
    sid = str(uuid.uuid4())
    await client.post("/v1/surveys", json={"id": sid, "title": {"default": "S"}}, headers=h)
    await client.put(f"/v1/surveys/{sid}/versions/1", json={"definition": DEF}, headers=h)
    await client.post(f"/v1/surveys/{sid}/versions/1/publish", headers=h)
    tok = (await client.post(f"/v1/surveys/{sid}/collectors", json={}, headers=h)).json()["token"]
    for t in texts:
        r = await client.post(f"/public/v1/c/{tok}/responses", json={"id": str(uuid.uuid4()), "answers": [{"q": "nps", "value": 5}, {"q": "why", "value": t}]})
        assert r.status_code == 200, r.text
    return u, org, h, sid


def base(sid):
    return f"/v1/surveys/{sid}/questions/why/semantic"


async def embedded(make_user, client, **kw):
    u, org, h, sid = await seed(make_user, client, **kw)
    r = await client.post(base(sid) + "/embed", json={}, headers=h)
    assert r.status_code == 200, r.text
    return u, org, h, sid


async def frozen_taxonomy(app, client, h, sid):
    app.state.container.llm.themes = THEMES
    p = f"/v1/surveys/{sid}/questions/why/taxonomy"
    assert (await client.post(p + "/propose", headers=h)).status_code == 201
    tax = (await client.get(p, headers=h)).json()["versions"][-1]
    for t in tax["themes"]:
        await client.post(p + f"/{tax['version']}/themes/{t['id']}/decide", json={"action": "approve"}, headers=h)
    assert (await client.post(p + f"/{tax['version']}/freeze", headers=h)).status_code == 200
    return tax["version"]


# ---------- embed ----------
async def test_embed_then_replay_skips_same_source_hash(make_user, client, app):
    u, org, h, sid = await seed(make_user, client)
    r = (await client.post(base(sid) + "/embed", json={}, headers=h)).json()
    n = len(NEG + POS + OTHER)
    assert r["embedded"] == n and r["skipped"] == 0 and r["remaining"] == 0 and r["model_id"] == app.state.container.embedder.model_id
    again = (await client.post(base(sid) + "/embed", json={}, headers=h)).json()
    assert again["embedded"] == 0 and again["skipped"] == n


async def test_embed_limit_batches(make_user, client):
    u, org, h, sid = await seed(make_user, client)
    r = (await client.post(base(sid) + "/embed", json={"limit": 5}, headers=h)).json()
    assert r["embedded"] == 5 and r["remaining"] == len(NEG + POS + OTHER) - 5
    r2 = (await client.post(base(sid) + "/embed", json={"limit": 500}, headers=h)).json()
    assert r2["embedded"] == r["remaining"] and r2["skipped"] == 5


@pytest.mark.parametrize("body", [{"limit": 0}, {"limit": 501}, {"limit": -1}, {"limit": "x"}, {"limit": 1.5}, {"bogus": 1}, {"limit": None}])
async def test_embed_rejects_bad_bodies(make_user, client, body):
    u, org, h, sid = await seed(make_user, client, texts=["terrible"])
    assert (await client.post(base(sid) + "/embed", json=body, headers=h)).status_code == 422


async def test_embed_rejects_bad_question_unauth_and_other_org(make_user, client):
    u, org, h, sid = await seed(make_user, client, texts=["terrible"])
    assert (await client.post(f"/v1/surveys/{sid}/questions/1bad/semantic/embed", json={}, headers=h)).status_code == 422
    assert (await client.post(base(sid) + "/embed", json={})).status_code in (401, 403)
    assert (await client.post(base(sid) + "/embed", json={}, headers=u.headers(uuid.uuid4()))).status_code == 403


async def test_embed_skips_gibberish(make_user, client):
    u, org, h, sid = await seed(make_user, client, texts=["???", "ok", "terrible"])
    assert (await client.post(base(sid) + "/embed", json={}, headers=h)).json()["embedded"] == 1   # "???" and "ok" are not informative


# ---------- cluster ----------
def labeller(llm):
    def f(clusters):
        out = []
        for c in clusters:
            txt = " ".join(e["text"] for e in c["examples"])
            neg = any(w in txt for w in ("terrible", "awful", "زفت", "سيء"))
            out.append({"cluster_no": c["cluster_no"], "label": "تجربة سيئة" if neg else "Positive experience", "description": "وصف قصير" if neg else "Happy respondents.",
                        "verbatim_ids": [c["examples"][0]["id"]]})
        return out
    llm.cluster_labels = f


async def test_cluster_labels_stored_and_listed_with_arabic_roundtrip(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    labeller(app.state.container.llm)
    r = await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["k"] == 2 and r.json()["labelled"] == 2
    d = (await client.get(base(sid) + "/clusters", headers=h)).json()
    assert d["run"]["k"] == 2 and len(d["clusters"]) == 2
    assert sorted(c["size"] for c in d["clusters"]) == [8, 9] and d["unclustered"] == 0     # k-means places every point; only undersized clusters become 'unclustered' 
    labels = {c["label"] for c in d["clusters"]}
    assert labels == {"تجربة سيئة", "Positive experience"} and all(not c["unlabelled"] for c in d["clusters"])
    for c in d["clusters"]:
        assert len(c["examples"]) == 3 and all(e["text"] in NEG + POS for e in c["examples"])
    neg = next(c for c in d["clusters"] if c["label"] == "تجربة سيئة")
    assert all(e["text"] in NEG for e in neg["examples"]) and neg["description"] == "وصف قصير"


async def test_cluster_replay_is_cached_and_appends_nothing(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    labeller(app.state.container.llm)
    a = (await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)).json()
    b = (await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)).json()
    assert b == {"run_id": a["run_id"], "cached": True}
    c = (await client.post(base(sid) + "/cluster", json={"k": 3}, headers=h)).json()          # different params -> new run, latest wins
    assert c["cached"] is False and c["run_id"] != a["run_id"]
    assert (await client.get(base(sid) + "/clusters", headers=h)).json()["run"]["run_id"] == c["run_id"]


async def test_bad_llm_labels_leave_cluster_unlabelled(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    app.state.container.llm.cluster_labels = lambda cl: [
        {"cluster_no": 0, "label": "Looks fine", "description": "d", "verbatim_ids": [str(uuid.uuid4())]},            # not a member
        {"cluster_no": 1, "label": "x" * 80, "description": "d", "verbatim_ids": [cl[1]["examples"][0]["id"]]}]       # too long
    assert (await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)).json()["labels_dropped"] == 2
    d = (await client.get(base(sid) + "/clusters", headers=h)).json()
    assert all(c["unlabelled"] and c["label"] is None for c in d["clusters"]) and len(d["clusters"]) == 2


async def test_llm_outage_leaves_clusters_unlabelled(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)

    def boom(_):
        raise RuntimeError("down")
    app.state.container.llm.cluster_labels = boom
    assert (await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)).status_code == 201
    assert all(c["unlabelled"] for c in (await client.get(base(sid) + "/clusters", headers=h)).json()["clusters"])


async def test_cluster_needs_embeddings(make_user, client):
    u, org, h, sid = await seed(make_user, client)
    assert (await client.post(base(sid) + "/cluster", json={}, headers=h)).status_code == 409
    assert (await client.get(base(sid) + "/clusters", headers=h)).json() == {"run": None, "clusters": []}


@pytest.mark.parametrize("body", [{"min_size": 4}, {"min_size": 0}, {"k_max": 1}, {"k_max": 51}, {"k": 0}, {"k": 51}, {"k": "two"}, {"bogus": True}, {"min_size": 1001}])
async def test_cluster_rejects_bad_bodies(make_user, client, body):
    u, org, h, sid = await seed(make_user, client, texts=["terrible"])
    assert (await client.post(base(sid) + "/cluster", json=body, headers=h)).status_code == 422


async def test_respondent_text_reaches_label_call_inside_data_tags(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    c = app.state.container
    sent = []

    class Msgs:
        async def create(self, **kw):
            sent.append(kw)
            return NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps({"labels": []}))], usage=NS(input_tokens=1, output_tokens=1))
    real = c.llm
    c.llm = AnthropicLLM(client=NS(beta=NS(messages=Msgs()), messages=Msgs()))
    try:
        assert (await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)).status_code == 201
    finally:
        c.llm = real
    content = sent[0]["messages"][0]["content"]
    body = content.split("<data>", 1)[1].rsplit("</data>", 1)[0]
    assert "terrible" in body and "</data>" not in body and content.rstrip().endswith("</data>")


# ---------- assign ----------
async def test_assign_bands_counts_review_queue_and_keyword_tagging_untouched(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    assert (await client.post(base(sid) + "/assign", json={"taxonomy_version": 1}, headers=h)).status_code == 409        # no frozen taxonomy yet
    v = await frozen_taxonomy(app, client, h, sid)
    tag = (await client.post(f"/v1/surveys/{sid}/questions/why/taxonomy/{v}/tag", headers=h)).json()
    r = await client.post(base(sid) + "/assign", json={"taxonomy_version": v}, headers=h)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["method"] == "semantic" and j["assigned"] + j["review"] + j["other"] == 17 and j["assigned"] >= 4
    d = (await client.get(base(sid) + "/assignments", headers=h)).json()
    assert d["method"] == "semantic" and d["run"]["taxonomy_version"] == v
    other = [x for x in d["counts"] if x["theme"] == "other"]
    assert other == [] or all(x["suppressed"] for x in other)                          # a single 'other' answer is below min-n
    tot = sum(x["n"] or 0 for x in d["counts"])
    assert tot <= 17
    assert all(set(q) >= {"response_id", "text", "score", "theme_key", "keyword_themes"} for q in d["review_queue"])
    again = (await client.post(f"/v1/surveys/{sid}/questions/why/taxonomy/{v}/tag", headers=h)).json()
    assert again["cached"] and again["tagged"] == tag["tagged"]                         # keyword method not overridden


async def test_assign_low_threshold_never_forces_unrelated_text(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    v = await frozen_taxonomy(app, client, h, sid)
    j = (await client.post(base(sid) + "/assign", json={"taxonomy_version": v, "high": 0.95, "low": 0.9}, headers=h)).json()
    assert j["other"] >= 1


async def test_assign_replay_cached_and_changed_thresholds_append_new_run(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    v = await frozen_taxonomy(app, client, h, sid)
    a = (await client.post(base(sid) + "/assign", json={"taxonomy_version": v}, headers=h)).json()
    b = (await client.post(base(sid) + "/assign", json={"taxonomy_version": v}, headers=h)).json()
    assert b == {"run_id": a["run_id"], "cached": True}
    c = (await client.post(base(sid) + "/assign", json={"taxonomy_version": v, "high": 0.8, "low": 0.4}, headers=h)).json()
    assert c["cached"] is False and (await client.get(base(sid) + "/assignments", headers=h)).json()["run"]["run_id"] == c["run_id"]


async def test_assign_draft_taxonomy_refused(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    app.state.container.llm.themes = THEMES
    await client.post(f"/v1/surveys/{sid}/questions/why/taxonomy/propose", headers=h)
    assert (await client.post(base(sid) + "/assign", json={"taxonomy_version": 1}, headers=h)).status_code == 409


@pytest.mark.parametrize("body", [{}, {"taxonomy_version": 0}, {"taxonomy_version": "a"}, {"taxonomy_version": 1, "high": 0.4, "low": 0.5},
                                  {"taxonomy_version": 1, "high": 0.5, "low": 0.5}, {"taxonomy_version": 1, "high": 1.5}, {"taxonomy_version": 1, "low": 0},
                                  {"taxonomy_version": 1, "low": 1}, {"taxonomy_version": 1, "x": 1}])
async def test_assign_rejects_bad_bodies(make_user, client, body):
    u, org, h, sid = await seed(make_user, client, texts=["terrible"])
    assert (await client.post(base(sid) + "/assign", json=body, headers=h)).status_code == 422


async def test_assignments_empty(make_user, client):
    u, org, h, sid = await seed(make_user, client, texts=["terrible"])
    d = (await client.get(base(sid) + "/assignments", headers=h)).json()
    assert d["run"] is None and d["counts"] == [] and d["review_queue"] == []
    assert (await client.get(base(sid) + "/assignments?taxonomy_version=0", headers=h)).status_code == 422


# ---------- search ----------
async def test_search_returns_original_text_nearest_first(make_user, client):
    u, org, h, sid = await embedded(make_user, client)
    r = await client.get(base(sid) + "/search", params={"q": "awful", "k": 4}, headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["n"] == 17 and len(d["results"]) == 4
    assert all(x["text"] in NEG for x in d["results"]) and d["results"] == sorted(d["results"], key=lambda x: -x["score"])
    ar = (await client.get(base(sid) + "/search", params={"q": "زفت", "k": 20}, headers=h)).json()
    assert {x["text"] for x in ar["results"][:8]} == set(NEG)


async def test_search_hidden_below_min_n_and_before_embedding(make_user, client):
    u, org, h, sid = await seed(make_user, client, texts=["terrible", "awful", "excellent"])
    await client.post(base(sid) + "/embed", json={}, headers=h)
    d = (await client.get(base(sid) + "/search", params={"q": "terrible"}, headers=h)).json()
    assert d["results"] == [] and "minimum" in d["hidden"] and d["n"] == 3


@pytest.mark.parametrize("params", [{"q": "a"}, {"q": ""}, {"q": "x" * 201}, {"q": "ok", "k": 0}, {"q": "ok", "k": 21}, {"q": "ok", "k": "x"}, {}])
async def test_search_rejects_bad_params(make_user, client, params):
    u, org, h, sid = await seed(make_user, client, texts=["terrible"])
    assert (await client.get(base(sid) + "/search", params=params, headers=h)).status_code == 422


async def test_search_whitespace_only_query_rejected(make_user, client):
    u, org, h, sid = await seed(make_user, client, texts=["terrible"])
    assert (await client.get(base(sid) + "/search", params={"q": "   "}, headers=h)).status_code == 422


async def test_search_skips_excluded_responses(make_user, client):
    u, org, h, sid = await embedded(make_user, client)
    top = (await client.get(base(sid) + "/search", params={"q": "terrible", "k": 1}, headers=h)).json()["results"][0]
    ex = await client.post(f"/v1/surveys/{sid}/responses/{top['response_id']}/exclude", json={"excluded": True, "reason": "test"}, headers=h)
    assert ex.status_code == 200, ex.text
    d = (await client.get(base(sid) + "/search", params={"q": "terrible", "k": 20}, headers=h)).json()
    assert top["response_id"] not in {x["response_id"] for x in d["results"]} and d["n"] == 16


# ---------- security ----------
@pytest.mark.security
async def test_other_model_embeddings_are_never_compared(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    e = app.state.container.embedder
    rid = (await client.get(base(sid) + "/search", params={"q": "awful", "k": 1}, headers=h)).json()["results"][0]["response_id"]
    async with tenant_tx(app.state.pool, None, org) as c:                    # a vector from another model with a different dimension, right on top of the query
        await c.execute("insert into text_embeddings(org_id,response_id,question_id,model_id,dim,source_hash,vec) values($1,$2,'why','other-model-3d',3,'x','[1,0,0]')", uuid.UUID(org), uuid.UUID(rid))
    d = (await client.get(base(sid) + "/search", params={"q": "awful", "k": 20}, headers=h)).json()
    assert d["model_id"] == e.model_id and d["n"] == 17 and len(d["results"]) == 17
    assert (await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)).status_code == 201


@pytest.mark.security
async def test_semantic_endpoints_tenant_isolated(make_user, client, app):
    u, org, h, sid = await embedded(make_user, client)
    labeller(app.state.container.llm)
    await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)
    v2 = make_user(); o2 = await v2.create_org(); h2 = v2.headers(o2)
    assert (await client.get(base(sid) + "/clusters", headers=h2)).json() == {"run": None, "clusters": []}
    assert (await client.get(base(sid) + "/assignments", headers=h2)).json()["run"] is None
    s = (await client.get(base(sid) + "/search", params={"q": "awful"}, headers=h2)).json()
    assert s["results"] == [] and s["n"] == 0
    assert (await client.post(base(sid) + "/embed", json={}, headers=h2)).json()["embedded"] == 0
    assert (await client.post(base(sid) + "/cluster", json={}, headers=h2)).status_code == 409
    assert (await client.get(base(sid) + "/clusters", headers=v2.headers(uuid.uuid4()))).status_code == 403


@pytest.mark.security
async def test_processor_switched_off_blocks_llm_paths(make_user, client):
    u, org, h, sid = await embedded(make_user, client)
    assert (await client.put("/v1/privacy/processors/llm", json={"enabled": False}, headers=h)).status_code == 200
    for method, path, kw in [("post", "/embed", {"json": {}}), ("post", "/cluster", {"json": {}}), ("get", "/search", {"params": {"q": "awful"}})]:
        assert (await getattr(client, method)(base(sid) + path, headers=h, **kw)).status_code == 403


@pytest.mark.security
async def test_free_plan_without_credits_blocks_embed_and_cluster(make_user, client):
    u, org, h, sid = await embedded(make_user, client)
    assert (await client.post("/v1/billing/change-plan", json={"plan": "free"}, headers=h)).status_code == 200
    for path in ("/embed", "/cluster"):
        r = await client.post(base(sid) + path, json={}, headers=h)
        assert r.status_code == 402 and "plan_limit" in r.text


async def test_the_labelling_prompt_holds_no_database_id_and_stored_labels_point_at_real_answers(make_user, client, app):
    import json
    import re
    u, org, h, sid = await embedded(make_user, client)
    llm = app.state.container.llm
    labeller(llm)
    llm.calls.clear()
    assert (await client.post(base(sid) + "/cluster", json={"k": 2}, headers=h)).status_code == 201
    sent = json.dumps([c for call in llm.calls if "clusters" in call for c in call["clusters"]], ensure_ascii=False)
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", sent)             # no UUID anywhere in what the model sees
    assert re.findall(r'"id": "(c\d+_\d+)"', sent)                                                          # examples carry c<cluster>_<n> ids
    d = (await client.get(base(sid) + "/clusters", headers=h)).json()
    assert all(not c["unlabelled"] for c in d["clusters"])                                                  # the opaque ids were mapped back, so verification passed
