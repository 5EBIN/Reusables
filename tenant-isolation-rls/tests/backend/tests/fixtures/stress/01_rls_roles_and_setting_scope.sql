\set ON_ERROR_STOP off
drop database if exists t1; create database t1;
\c t1
create role app_owner nologin; create role api_user login password 'x' nobypassrls;
create schema app authorization app_owner; grant create, usage on schema public to app_owner; grant usage on schema public to api_user;
set role app_owner;
create table public.answers(id serial primary key, tenant_id uuid not null, v int);
insert into public.answers(tenant_id,v) select (case when g%2=0 then 'aaaaaaaa-0000-0000-0000-000000000001' else 'bbbbbbbb-0000-0000-0000-000000000002' end)::uuid, g from generate_series(1,10) g;
alter table public.answers enable row level security;
create or replace function app.current_org() returns uuid language sql stable as $$ select nullif(current_setting('app.tenant_id', true),'')::uuid $$;
create policy iso on public.answers using (tenant_id = app.current_org()) with check (tenant_id = app.current_org());
reset role;
grant usage on schema app to api_user; grant select,insert on public.answers to api_user; grant usage on sequence answers_id_seq to api_user;

\echo '--- T1: table OWNER, RLS enabled but not FORCED (expect: sees ALL rows)'
set role app_owner; begin; set local app.tenant_id='aaaaaaaa-0000-0000-0000-000000000001'; select count(*) as owner_sees from public.answers; commit; reset role;

\echo '--- T2: owner with FORCE ROW LEVEL SECURITY (expect: 5)'
alter table public.answers force row level security;
set role app_owner; begin; set local app.tenant_id='aaaaaaaa-0000-0000-0000-000000000001'; select count(*) from public.answers; commit; reset role;

\echo '--- T3: superuser (postgres) bypasses RLS even with FORCE (expect 10)'
begin; set local app.tenant_id='aaaaaaaa-0000-0000-0000-000000000001'; select count(*) as superuser_sees from public.answers; commit;

\echo '--- T4: api_user + SET LOCAL tenant A (expect 5)'
set role api_user; begin; set local app.tenant_id='aaaaaaaa-0000-0000-0000-000000000001'; select count(*) from public.answers; commit;

\echo '--- T5: session-level SET leaks into the next request on a pooled connection (expect 5 = LEAK, no tenant set by 2nd request)'
set app.tenant_id='aaaaaaaa-0000-0000-0000-000000000001';
begin; select count(*) as next_request_without_setting from public.answers; commit;
reset app.tenant_id;

\echo '--- T6: after a committed SET LOCAL txn, setting reads as empty string not NULL; policy must fail closed (expect 0)'
begin; set local app.tenant_id='aaaaaaaa-0000-0000-0000-000000000001'; commit;
select current_setting('app.tenant_id', true) is null as is_null, current_setting('app.tenant_id', true)='' as is_empty;
select count(*) as no_tenant_rows from public.answers;

\echo '--- T7: WITH CHECK blocks writing into another tenant (expect error)'
begin; set local app.tenant_id='aaaaaaaa-0000-0000-0000-000000000001'; insert into public.answers(tenant_id,v) values ('bbbbbbbb-0000-0000-0000-000000000002',99); rollback;

\echo '--- T8: forgot nullif -> malformed empty string cast (shows the failure mode of the naive policy)'
select ''::uuid;
