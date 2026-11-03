import uuid

import asyncpg
import pytest

from app.db import create_pool, tenant_tx
from tests.dsn import API as API_DSN
from tests.dsn import OWNER as OWNER_DSN

A, B = str(uuid.uuid4()), str(uuid.uuid4())
RUN, RID, SID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

# table -> (insert sql taking org_id as $1, update sql, delete sql)
INSERTS = {
    "text_embeddings": "insert into text_embeddings(org_id,response_id,question_id,model_id,dim,source_hash,vec) values($1,gen_random_uuid(),'why','m',2,'h','[1,0]')",
    "semantic_clusters": "insert into semantic_clusters(org_id,run_id,survey_id,question_id,model_id,k,inputs_hash) values($1,gen_random_uuid(),gen_random_uuid(),'why','m',2,gen_random_uuid()::text)",
    "semantic_cluster_members": "insert into semantic_cluster_members(org_id,run_id,response_id,cluster_no,distance) values($1,gen_random_uuid(),gen_random_uuid(),0,0.1)",
    "semantic_cluster_labels": "insert into semantic_cluster_labels(org_id,run_id,cluster_no,label,description,verbatim_ids,proposed_by,model) values($1,gen_random_uuid(),0,'l','d','{}','llm','m')",
    "theme_assignments": "insert into theme_assignments(org_id,survey_id,question_id,taxonomy_version,response_id,theme_key,score,band,method,model_id,run_id) "
                         "values($1,gen_random_uuid(),'why',1,gen_random_uuid(),'t',0.9,'assigned','semantic','m',gen_random_uuid())",
    "rag_answers": "insert into rag_answers(org_id,id,survey_id,question_id,asked_by,question,status,model,prompt_version,inputs_hash) "
                   "values($1,gen_random_uuid(),gen_random_uuid(),'why',gen_random_uuid(),'what now','verified','m','p',gen_random_uuid()::text)",
}
UPDATES = {"text_embeddings": "update text_embeddings set dim=2", "semantic_clusters": "update semantic_clusters set k=3", "semantic_cluster_members": "update semantic_cluster_members set cluster_no=1",
           "semantic_cluster_labels": "update semantic_cluster_labels set label='x'", "theme_assignments": "update theme_assignments set band='review'", "rag_answers": "update rag_answers set status='unverified'"}


@pytest.fixture
async def pool():
    p = await create_pool(max_size=4)
    yield p
    await p.close()


@pytest.mark.security
@pytest.mark.parametrize("table", sorted(INSERTS))
async def test_tenant_isolation_per_table(pool, table):
    async with tenant_tx(pool, None, A) as c:
        await c.execute(INSERTS[table], uuid.UUID(A))
    async with tenant_tx(pool, None, B) as c:
        assert await c.fetchval(f"select count(*) from {table}") == 0
    async with tenant_tx(pool, None, A) as c:
        assert await c.fetchval(f"select count(*) from {table}") >= 1
    with pytest.raises(asyncpg.PostgresError):                          # WITH CHECK: cannot write into another tenant
        async with tenant_tx(pool, None, B) as c:
            await c.execute(INSERTS[table], uuid.UUID(A))
    async with tenant_tx(pool, None, None) as c:                        # no tenant context fails closed
        assert await c.fetchval(f"select count(*) from {table}") == 0


@pytest.mark.security
@pytest.mark.parametrize("table", sorted(INSERTS))
async def test_append_only_update_and_delete_denied(pool, table):
    async with tenant_tx(pool, None, A) as c:
        await c.execute(INSERTS[table], uuid.UUID(A))
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with tenant_tx(pool, None, A) as c:
            await c.execute(UPDATES[table])
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with tenant_tx(pool, None, A) as c:
            await c.execute(f"delete from {table}")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with tenant_tx(pool, None, A) as c:
            await c.execute(f"truncate {table}")


@pytest.mark.security
async def test_privileges_are_select_insert_only_and_rls_forced():
    c = await asyncpg.connect(OWNER_DSN)
    try:
        for t in INSERTS:
            privs = {r["privilege_type"] for r in await c.fetch("select privilege_type from information_schema.role_table_grants where grantee='app_api' and table_name=$1", t)}
            assert privs == {"SELECT", "INSERT"}, (t, privs)
            r = await c.fetchrow("select relrowsecurity, relforcerowsecurity from pg_class where relname=$1 and relnamespace='public'::regnamespace", t)
            assert r["relrowsecurity"] and r["relforcerowsecurity"]
    finally:
        await c.close()


async def test_embedding_dim_check_and_one_row_per_hash(pool):
    with pytest.raises(asyncpg.CheckViolationError):                    # stored dim must equal the vector's real dimension
        async with tenant_tx(pool, None, A) as c:
            await c.execute("insert into text_embeddings(org_id,response_id,question_id,model_id,dim,source_hash,vec) values($1,$2,'why','m',3,'h','[1,0]')", uuid.UUID(A), RID)
    async with tenant_tx(pool, None, A) as c:
        await c.execute("insert into text_embeddings(org_id,response_id,question_id,model_id,dim,source_hash,vec) values($1,$2,'why','m',2,'h','[1,0]')", uuid.UUID(A), RID)
    with pytest.raises(asyncpg.UniqueViolationError):
        async with tenant_tx(pool, None, A) as c:
            await c.execute("insert into text_embeddings(org_id,response_id,question_id,model_id,dim,source_hash,vec) values($1,$2,'why','m',2,'h','[0,1]')", uuid.UUID(A), RID)


async def test_band_and_label_checks(pool):
    with pytest.raises(asyncpg.CheckViolationError):
        async with tenant_tx(pool, None, A) as c:
            await c.execute(INSERTS["theme_assignments"].replace("'assigned'", "'bogus'"), uuid.UUID(A))
    with pytest.raises(asyncpg.CheckViolationError):
        async with tenant_tx(pool, None, A) as c:
            await c.execute(INSERTS["semantic_cluster_labels"].replace("'l','d'", f"'{'x' * 61}','d'"), uuid.UUID(A))
    assert API_DSN
