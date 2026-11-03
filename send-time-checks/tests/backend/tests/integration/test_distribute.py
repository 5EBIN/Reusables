import uuid

import pytest

from tests.integration.test_studio import survey_with

DEF = {"pages": [{"elements": [{"type": "rating", "name": "q1", "rateMin": 1, "rateMax": 5}]}]}


async def test_link_qr_embed(make_user, client):
    u = make_user(); org = await u.create_org(); h = u.headers(org)
    sid, tok = await survey_with(client, h, DEF)
    assert (await client.post(f"/v1/surveys/{sid}/distribution/link", json={"token": tok}, headers=h)).json()["url"].endswith(f"/s/{tok}?src=link")
    r = await client.post(f"/v1/surveys/{sid}/distribution/qr", json={"token": tok}, headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "image/svg+xml" and r.content.startswith(b"<?xml") and r.headers["cache-control"] == "no-store"
    e = (await client.post(f"/v1/surveys/{sid}/distribution/embed", json={"token": tok, "allowed_origin": "https://portal.example.ae", "height": 640}, headers=h)).json()
    assert e["snippet"].startswith("<iframe") and 'height="640"' in e["snippet"] and "src=embed&amp;embed=1" in e["snippet"] and e["frame_ancestors"] == "'self' https://portal.example.ae"
    p = (await client.post(f"/v1/surveys/{sid}/distribution/embed", json={"token": tok, "mode": "popup", "allowed_origin": "https://x.example.ae"}, headers=h)).json()
    assert p["snippet"].startswith("<script") and "/embed.js" in p["snippet"] and 'data-mode="popup"' in p["snippet"] and p["snippets"]["iframe"].startswith("<iframe")


@pytest.mark.security
async def test_distribution_validation_and_isolation(make_user, client):
    u = make_user(); org = await u.create_org(); h = u.headers(org)
    sid, tok = await survey_with(client, h, DEF)
    for bad in ({"allowed_origin": "http://x.com"}, {"allowed_origin": "https://x.com/path"}, {"allowed_origin": "https://x.com\" onload=\"x"}, {"allowed_origin": "javascript:alert(1)"}, {"height": 10}, {"mode": "script"}):
        assert (await client.post(f"/v1/surveys/{sid}/distribution/embed", json={"token": tok, "allowed_origin": "https://ok.example.ae"} | bad, headers=h)).status_code == 422, bad
    for t in ("short", "x" * 30, tok + "z", "bad token with spaces and more!!"):
        assert (await client.post(f"/v1/surveys/{sid}/distribution/qr", json={"token": t}, headers=h)).status_code in (404, 422)
    v = make_user(); org2 = await v.create_org(); h2 = v.headers(org2)
    assert (await client.post(f"/v1/surveys/{sid}/distribution/qr", json={"token": tok}, headers=h2)).status_code == 404            # other tenant's collector
    assert (await client.post(f"/v1/surveys/{uuid.uuid4()}/distribution/link", json={"token": tok}, headers=h)).status_code == 404
