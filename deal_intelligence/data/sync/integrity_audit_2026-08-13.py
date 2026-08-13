"""One-off data-integrity sweep across the Attio export and the hub snapshot,
looking for the same CLASS of problem as the AMCA stale-date case: duplicates,
contradictions, and values that quietly disagree between the two systems.
"""
import json
from collections import Counter, defaultdict
from datetime import date

from deal_intelligence import deal_sync as ds
from deal_intelligence.import_attio_deals_csv import (authoritative_row,
                                                      company_key_of,
                                                      group_by_company, read_rows)

CSV = '/Users/oscar/Downloads/Deals - Deals (15).csv'
rows = list(read_rows(CSV))
groups = group_by_company(rows)
attio = ds.attio_companies_from_csv(CSV)
snap = json.load(open('deal_intelligence/data/companies-snapshot.json'))
hub = ds.hub_companies_from_snapshot(snap)
raw = {c['id']: c for c in snap}
matched, hub_only, attio_only = ds.link(hub, attio)
TODAY = '2026-08-13'


def head(n, t):
    print(f'\n{"="*78}\n{n}. {t}\n{"="*78}')


# 1 ─ same company + same series twice in Attio
head(1, 'DUPLICATE ATTIO DEALS (same company AND same series)')
dupes = []
for k, g in groups.items():
    by_series = Counter((r['series'] or '(blank)') for r in g)
    for s, n in by_series.items():
        if n > 1:
            dupes.append((g[0]['name'], s, n))
for n, s, c in sorted(dupes):
    print(f'   {n[:40]:<42}{s:<16}{c} copies')
print(f'   -> {len(dupes)} cases')

# 2 ─ a non-authoritative deal with a LATER date than the one we picked
head(2, 'AUTHORITATIVE ROW IS NOT THE LATEST-DATED ROW')
bad = []
for k, g in groups.items():
    if len(g) < 2:
        continue
    a = authoritative_row(g)
    latest = max((r['deal_date'] for r in g if r['deal_date']), default='')
    if latest and a['deal_date'] != latest:
        bad.append((a['name'], a['deal_date'] or 'NONE', latest))
for n, chosen, latest in sorted(bad):
    print(f'   {n[:40]:<42}chose={chosen:<12}latest={latest}')
print(f'   -> {len(bad)} cases')

# 3 ─ deal dates in the future
head(3, 'DEAL DATE IN THE FUTURE (data-entry error)')
fut = sorted({(r['name'], r['deal_date']) for r in rows if r['deal_date'] > TODAY})
for n, d in fut:
    print(f'   {n[:40]:<42}{d}')
print(f'   -> {len(fut)} cases')

# 4 ─ same Attio record id twice
head(4, 'DUPLICATE ATTIO RECORD IDS')
rid = Counter(r['record_id'] for r in rows if r['record_id'])
print(f'   -> {sum(1 for v in rid.values() if v > 1)} cases')

# 5 ─ same company name on two different domains (beyond the key collisions)
head(5, 'SAME COMPANY NAME, DIFFERENT DOMAINS IN ATTIO')
byname = defaultdict(set)
for r in rows:
    if r['domain']:
        byname[ds.norm_name(r['name'])].add(r['domain'])
n5 = 0
for nm, doms in sorted(byname.items()):
    if len(doms) > 1:
        n5 += 1
        print(f'   {nm[:30]:<32}{sorted(doms)}')
print(f'   -> {n5} cases')

# 6 ─ hub docs whose stage is not a real stage
head(6, 'HUB DOCS WITH AN INVALID OR MISSING STAGE')
STAGES = {'new', 'watchlist', 'pipeline', 'qualified', 'radar', 'invested', 'passed'}
badstage = [(c['id'], c.get('name'), c.get('stage')) for c in snap
            if c.get('stage') not in STAGES]
for i, n, s in sorted(badstage)[:40]:
    print(f'   {i[:34]:<36}{str(n)[:28]:<30}stage={s!r}')
print(f'   -> {len(badstage)} cases')

# 7 ─ hub docs carrying a tag identical to their own stage
head(7, 'HUB DOCS WHERE A TAG DUPLICATES THE PRIMARY STAGE')
dup_tag = [(c['id'], c.get('stage')) for c in snap
           if c.get('stage') and c.get('stage') in (c.get('tags') or [])]
for i, s in sorted(dup_tag):
    print(f'   {i[:40]:<42}stage={s} also in tags')
print(f'   -> {len(dup_tag)} cases')

# 8 ─ hub round-docs whose parent is missing
head(8, 'HUB ROUND DOCS WITH NO PARENT DOC')
orph = [c['id'] for c in snap if '--' in c['id']
        and (c.get('companyKey') or c['id'].split('--')[0]) not in raw]
print('   ' + (', '.join(orph) if orph else 'none'))
print(f'   -> {len(orph)} cases')

# 9 ─ hub companies with no Attio deal AND no screen (dead docs)
head(9, 'HUB DOCS WITH NO ATTIO DEAL AND NO SCREEN')
mk = {h['key'] for h, _, _ in matched}
dead = [(r['key'], r['name'], r['stage']) for r in hub.values()
        if r['key'] not in mk and not r.get('latestScreen')]
for k, n, s in sorted(dead):
    print(f'   {k[:34]:<36}{str(n)[:28]:<30}stage={s}')
print(f'   -> {len(dead)} cases')

# 10 ─ Attio stage vs hub stage, straight disagreement on the primary
head(10, 'PRIMARY STAGE DISAGREES (Attio stage vs hub stage, ignoring tags)')
MAP = {'watchlist': 'watchlist', 'pipeline': 'pipeline', 'qualified': 'qualified',
       'radar': 'radar', 'invested': 'invested', 'passed': 'passed'}
diff = []
for h, a, _ in matched:
    want = MAP.get(str(a['stage']).strip().lower())
    if want and h['stage'] and h['stage'] != want:
        diff.append((a['name'], h['stage'], a['stage'], 'radar' in (h['tags'] or [])))
for n, hs, as_, _ in sorted(diff):
    print(f'   {n[:36]:<38}hub={hs:<12}attio={as_}')
print(f'   -> {len(diff)} cases (many are legitimate: hub keeps the additive tag)')

# 11 ─ round size wildly different order of magnitude
head(11, 'DEAL SIZE DIFFERS BY MORE THAN 2x BETWEEN HUB AND ATTIO')
big = []
for h, a, _ in matched:
    d = raw.get(h['key'], {})
    hs, as_ = d.get('roundSize'), a['deal_size']
    try:
        hs, as_ = float(hs), float(as_)
    except (TypeError, ValueError):
        continue
    if hs and as_ and (max(hs, as_) / min(hs, as_)) > 2:
        big.append((a['name'], hs, as_))
for n, hs, as_ in sorted(big):
    print(f'   {n[:36]:<38}hub=${hs/1e6:,.0f}M  attio=${as_/1e6:,.0f}M')
print(f'   -> {len(big)} cases')

# 12 ─ Attio deals with no associated company at all
head(12, 'ATTIO DEALS WITH NO DOMAIN (cannot key reliably)')
nod = sorted({r['name'] for r in rows if not r['domain']})
for n in nod:
    print(f'   {n}')
print(f'   -> {len(nod)} cases')
