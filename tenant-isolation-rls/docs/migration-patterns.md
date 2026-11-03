# Row-level security patterns, extracted from the migrations

The migrations are not copied. These are the three patterns that matter, with the original role names generalised: `<runtime_role>` is the role the API connects as
(`app_api` in these files), `<owner_role>` owns the tables and runs migrations (`app_owner`). Neither role may have `BYPASSRLS`.

## 1. Context functions and one helper that makes a table tenant-safe (migration 0001)

```sql
create schema if not exists app authorization <owner_role>;
grant usage on schema app to <runtime_role>;

-- the tenant and user are TRANSACTION-LOCAL settings, set by the application with set_config(..., true)
create or replace function app.current_org() returns uuid language sql stable as
  $$ select nullif(current_setting('app.tenant_id', true),'')::uuid $$;
create or replace function app.current_user_id() returns uuid language sql stable as
  $$ select nullif(current_setting('app.user_id', true),'')::uuid $$;

create or replace function app.apply_org_rls(tbl regclass) returns void language plpgsql as $f$
begin
  execute format('alter table %s enable row level security', tbl);
  execute format('alter table %s force row level security', tbl);      -- the table owner is subject to the policy too
  execute format('create policy org_iso on %s for all to <runtime_role>
                    using (org_id = (select app.current_org()))
                    with check (org_id = (select app.current_org()))', tbl);
end $f$;
```

Note `(select app.current_org())`: wrapping the function in a sub-select lets Postgres evaluate it once per statement instead of once per row.

## 2. Every tenant table: an `org_id` column, the helper, and minimal grants

```sql
create table public.team_invitations(
  org_id uuid not null, id uuid not null, email text not null, role text not null,
  token_hash text not null unique, expires_at timestamptz not null,
  primary key (org_id, id));
select app.apply_org_rls('public.team_invitations');
grant select, insert, update on public.team_invitations to <runtime_role>;      -- no delete unless the feature needs it
```

## 3. A role-aware policy, and an explicit policy for the owner role (migrations 0008 and 0080)

```sql
-- membership checks run in a SECURITY DEFINER function with a pinned search_path, so a policy can ask "is this user an admin of this org?"
create function app.is_org_admin(p_org uuid, p_user uuid) returns boolean
  language sql stable security definer set search_path = pg_catalog, public as
  $$ select exists (select 1 from public.memberships
        where org_id = p_org and user_id = p_user and role in ('client_admin','super_admin')
          and (expires_at is null or expires_at > now())) $$;
grant execute on function app.is_org_admin(uuid, uuid) to <runtime_role>;

create policy mem_admin_write on public.memberships for update to <runtime_role>
  using (org_id = (select app.current_org()) and app.is_org_admin(org_id, (select app.current_user_id())))
  with check (org_id = (select app.current_org()));

-- because RLS is FORCED, the owner role has no access unless a policy grants it; give it exactly what a platform screen needs
create policy plat_org_settings_owner on public.org_settings for select to <owner_role> using (true);
```

Consequences to remember:
* A role can only touch a table if it has BOTH a grant and a policy. Read-only for the owner role (the last policy) means an INSERT as the owner fails with "new row violates row-level security policy" even though the owner owns the table.
* Run the application's writes through the runtime role with the tenant set (`db/__init__.py: tenant_tx`). Never use a session-level `SET`, because a connection pooler in transaction mode would carry it to another tenant.
* Test it: `tests/integration/test_rls.py` and `tests/regression/test_pooler.py`.
