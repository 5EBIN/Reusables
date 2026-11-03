\set ON_ERROR_STOP on
drop database if exists stk; create database stk;
\c stk
create schema app authorization app_owner; grant create, usage on schema public to app_owner;
grant usage on schema app to api_user;
set role app_owner;
create function app.current_org() returns uuid language sql stable as $$ select nullif(current_setting('app.tenant_id', true),'')::uuid $$;
create table public.responses(id uuid primary key, tenant_id uuid not null, survey_id uuid not null, locale text, completed_at timestamptz default now());
create table public.answers(response_id uuid not null references public.responses(id), tenant_id uuid not null, question_id int not null, value_num double precision, value_text text, primary key(response_id, question_id));
create index answers_t_q on public.answers(tenant_id, question_id);
create index responses_t_s on public.responses(tenant_id, survey_id);
alter table public.responses enable row level security; alter table public.responses force row level security;
alter table public.answers enable row level security; alter table public.answers force row level security;
create policy iso_r on public.responses for all to api_user using (tenant_id=(select app.current_org())) with check (tenant_id=(select app.current_org()));
create policy iso_a on public.answers   for all to api_user using (tenant_id=(select app.current_org())) with check (tenant_id=(select app.current_org()));
reset role;
grant usage on schema public to api_user;
grant select,insert on public.responses, public.answers to api_user;
