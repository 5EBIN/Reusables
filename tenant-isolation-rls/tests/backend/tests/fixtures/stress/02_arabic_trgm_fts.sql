\set ON_ERROR_STOP off
drop database if exists ar_c; create database ar_c template template0 encoding 'UTF8' lc_collate 'C' lc_ctype 'C';
drop database if exists ar_u; create database ar_u template template0 encoding 'UTF8' lc_collate 'C.UTF-8' lc_ctype 'C.UTF-8';
\c ar_c
create extension pg_trgm;
\echo '=== DB ctype=C  : trigrams of an Arabic word'
select show_trgm('الخدمة') as trgm_c;
select similarity('الخدمة','الخدمه') as sim_taMarbuta_vs_ha_c;
\c ar_u
create extension pg_trgm;
\echo '=== DB ctype=C.UTF-8 : trigrams of an Arabic word'
select show_trgm('الخدمة') as trgm_u8;
select similarity('الخدمة','الخدمه') as sim_raw;
create function ar_norm(t text) returns text language sql immutable as $$
  select regexp_replace(
           translate(regexp_replace(t, '[\u064B-\u0652\u0640]', '', 'g'),
                     'أإآٱىةی', 'اااايهي'),
         '\s+',' ','g') $$;
select ar_norm('الخدمةُ بطيئةٌ جداً') as normalized;
select similarity(ar_norm('الخدمة'), ar_norm('الخدمه')) as sim_normalized;
\echo '=== FTS simple on Arabic: raw vs normalized, singular/plural/typo'
select to_tsvector('simple','الخدمة بطيئة جداً') @@ websearch_to_tsquery('simple','بطيئه') as raw_match_ha_variant;
select to_tsvector('simple',ar_norm('الخدمة بطيئة جداً')) @@ websearch_to_tsquery('simple',ar_norm('بطيئه')) as norm_match_ha_variant;
select to_tsvector('simple',ar_norm('الخدمة بطيئة')) @@ websearch_to_tsquery('simple',ar_norm('بطء')) as stem_gap_root_variant;
select to_tsvector('simple',ar_norm('الموظفون متعاونون')) @@ websearch_to_tsquery('simple',ar_norm('موظف')) as plural_vs_singular;
select to_tsvector('simple','الموظفون') ;
\echo '=== injection-ish text as bound-style literal into websearch_to_tsquery'
select websearch_to_tsquery('simple', $$'; drop table answers; -- OR "a b" -c$$) as safe_parse;
