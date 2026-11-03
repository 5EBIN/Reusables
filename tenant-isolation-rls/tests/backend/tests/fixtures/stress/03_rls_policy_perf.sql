\c t1
\set ON_ERROR_STOP off
drop policy if exists a_fn on public.big; drop policy if exists b_sel on public.big;
create policy a_fn on public.big for select to api_user using (tenant_id = app.current_org());
\echo '=== A (function directly): tenant 7, q=7, 3 runs'
set role api_user; begin; set local app.tenant_id='00000000-0000-0000-0000-000000000007';
explain (analyze, costs off, timing off, summary on) select count(*), avg(v) from public.big where q=7;
explain (analyze, costs off, timing off, summary on) select count(*), avg(v) from public.big where q=7;
explain (analyze, costs off, timing off, summary on) select date_trunc('month',created) m, count(*), avg(v) from public.big group by 1;
commit; reset role;
drop policy a_fn on public.big;
create policy b_sel on public.big for select to api_user using (tenant_id = (select app.current_org()));
\echo '=== B ((select function)): same'
set role api_user; begin; set local app.tenant_id='00000000-0000-0000-0000-000000000007';
explain (analyze, costs off, timing off, summary on) select count(*), avg(v) from public.big where q=7;
explain (analyze, costs off, timing off, summary on) select count(*), avg(v) from public.big where q=7;
explain (analyze, costs off, timing off, summary on) select date_trunc('month',created) m, count(*), avg(v) from public.big group by 1;
commit; reset role;
\echo '=== Policy that does a membership subquery per row-check (naive multi-org consultant policy)'
drop policy b_sel on public.big;
create table public.memberships(user_id uuid, org_id uuid);
insert into public.memberships select gen_random_uuid(), ('00000000-0000-0000-0000-'||lpad(g::text,12,'0'))::uuid from generate_series(0,49) g;
alter table public.memberships owner to app_owner; grant select on public.memberships to api_user;
create policy c_mem on public.big for select to api_user using (tenant_id in (select org_id from public.memberships where org_id = tenant_id));
set role api_user; begin;
explain (analyze, costs off, timing off, summary on) select count(*), avg(v) from public.big where q=7 and tenant_id='00000000-0000-0000-0000-000000000007';
commit; reset role;
