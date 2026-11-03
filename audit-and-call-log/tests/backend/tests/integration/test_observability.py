import pytest


async def test_health_ready_and_request_id(client):
    assert (await client.get("/healthz")).json() == {"ok": True}
    r = await client.get("/readyz")
    assert r.status_code == 200 and r.json() == {"ready": True}
    r = await client.get("/healthz", headers={"X-Request-ID": "abcd1234-ef56"})
    assert r.headers["X-Request-ID"] == "abcd1234-ef56"
    r = await client.get("/healthz", headers={"X-Request-ID": "bad id with spaces <script>"})
    assert r.headers["X-Request-ID"] != "bad id with spaces <script>" and len(r.headers["X-Request-ID"]) == 32          # untrusted ids replaced


async def test_metrics_off_without_token_and_scrubbed(client, monkeypatch):
    assert (await client.get("/metrics")).status_code == 404
    monkeypatch.setenv("METRICS_TOKEN", "m-secret-token")
    assert (await client.get("/metrics")).status_code == 404
    assert (await client.get("/metrics", headers={"Authorization": "Bearer wrong"})).status_code == 404
    await client.get("/public/v1/c/" + "Z" * 43 + "/survey")
    out = (await client.get("/metrics", headers={"Authorization": "Bearer m-secret-token"})).text
    assert "app_http_requests_total" in out and "Z" * 43 not in out and "/public/v1/c/{token}/survey" in out


@pytest.mark.security
async def test_logs_contain_no_secrets_or_raw_org(client, caplog):
    import logging
    import uuid
    org = str(uuid.uuid4())
    with caplog.at_level(logging.INFO, logger="app.access"):
        await client.get("/v1/me", headers={"Authorization": "Bearer <token>", "X-Org-Id": org})
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "super-secret-bearer-value" not in text and org not in text and '"status": 401' in text
