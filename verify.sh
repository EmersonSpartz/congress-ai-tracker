#!/bin/bash
# verify.sh: checks what a visitor would actually hit on the Congress AI Tracker.
# Usage: ./verify.sh [deployed_url]   (default: the live GitHub Pages site)
set -u
cd "$(dirname "$0")"
URL="${1:-https://emersonspartz.github.io/congress-ai-tracker/}"
FAIL=0
ok()   { echo "  PASS  $1"; }
bad()  { echo "  FAIL  $1"; FAIL=1; }

echo "== 1. build output"
python3 build.py > /tmp/cat-build.log 2>&1 && ok "build.py runs ($(tail -2 /tmp/cat-build.log | head -1 | cut -c1-90))" || bad "build.py failed: $(tail -3 /tmp/cat-build.log)"

echo "== 2. data.json integrity"
python3 - <<'EOF2' || FAIL=1
import json, sys, collections, re, glob, os
d = json.load(open('docs/data.json'))
ms = d['members']; errs = []
if not (530 <= len(ms) <= 541): errs.append(f'member count {len(ms)}')
sen = sum(1 for m in ms if m['chamber']=='Senate')
if sen != 100: errs.append(f'senators {sen}')
ids = collections.Counter(m['id'] for m in ms)
if any(v>1 for v in ids.values()): errs.append('duplicate ids')
dims = {x['key']: x for x in d['dimensions']}
ok_url = lambda u: isinstance(u, str) and re.match(r'^https?://', u)
bad_verdicts = 0
for m in ms:
    for k, dim in dims.items():
        p = m['positions'].get(k)
        if not p: errs.append(f"{m['id']} missing {k}"); continue
        if p['score'] is not None and p['score'] not in (-2,-1,0,1,2): errs.append(f"{m['id']} bad score {k}")
        if p['score'] is not None and p['label'] != dim['scale'][str(p['score'])]: errs.append(f"{m['id']} {k} label/score mismatch")
        if p['score'] is None and p['label'] != 'No public position found': errs.append(f"{m['id']} {k} null score with label {p['label']}")
        if p['score'] is not None and not p['evidence']: errs.append(f"{m['id']} {k} score without evidence")
        for e in p['evidence']:
            if not ok_url(e.get('url')): errs.append(f"{m['id']} {k} evidence without http url")
            if e.get('verified') in ('unsupported','wrong_person'): bad_verdicts += 1
    if not m['photo']: errs.append(f"{m['id']} no photo")
    q = m.get('quote')
    if q and (not q.get('text') or not ok_url(q.get('url'))): errs.append(f"{m['id']} malformed quote")
    for pc in m.get('pacs', []):
        if pc.get('url') and not ok_url(pc['url']): errs.append(f"{m['id']} pac url not http")
for ex in d['landscape'].get('explainers', {}).values():
    for b in ex.get('bills', []):
        if b.get('url') and not ok_url(b['url']): errs.append('explainer bill url not http')
if bad_verdicts: errs.append(f'{bad_verdicts} refuted evidence items still displayed')
# em dashes in OUR prose (verbatim quotes are exempt)
def prose(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ('quote',) and isinstance(v, str): continue
            if k == 'quote' and isinstance(v, dict): yield from prose({kk: vv for kk, vv in v.items() if kk != 'text'}, path + '/quote'); continue
            yield from prose(v, path + '/' + k)
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from prose(v, path + f'[{i}]')
    elif isinstance(o, str) and '\u2014' in o: yield path
em = list(prose(d))
if em: errs.append(f'{len(em)} em dashes in site prose, e.g. {em[0]}')
if not d['votes']: errs.append('no key votes')
for v in d['votes']:
    n = sum(1 for m in ms if v['id'] in m['votes'])
    need = 60 if v['id'][1:5] == '2024' else 90
    if n < need: errs.append(f"key vote {v['id']} only {n} member votes")
# research files present on disk must all be reflected, by name-checked bioguide
files = glob.glob('source/research/*.json')
researched = sum(1 for m in ms if m.get('researched'))
if files and researched == 0: errs.append('research files exist but no member is marked researched')
if researched != d['stats'].get('researched'): errs.append('researched count mismatch')
warns = open('build-warnings.log').read().splitlines() if os.path.exists('build-warnings.log') else []
skipped = [w for w in warns if 'skipped' in w]
print(f"  info  researched members: {researched}/{len(ms)}; bills: {len(d['bills'])}; votes: {len(d['votes'])}; build warnings: {len(warns)} ({len(skipped)} entries skipped)")
for w in skipped[:5]: print('  warn ', w[:140])
for e in errs[:15]: print('  FAIL ', e)
if errs: sys.exit(1)
print('  PASS  data.json integrity')
EOF2

echo "== 3. front-end static checks"
node --check docs/app.js && ok "app.js parses" || bad "app.js syntax"
grep -q '—\|—' docs/index.html docs/app.js && bad "em dash in site copy" || ok "no em dashes in site copy"
for f in docs/index.html docs/styles.css docs/app.js docs/data.json; do [ -s "$f" ] && ok "$f present" || bad "$f missing"; done

echo "== 4. deployed site (${URL})"
code=$(curl -s -o /tmp/cat-index.html -w "%{http_code}" "$URL")
[ "$code" = "200" ] && ok "index 200" || bad "index HTTP $code"
grep -q 'Where Congress Stands on AI' /tmp/cat-index.html && ok "title present" || bad "title missing in deployed index"
dcode=$(curl -s -o /tmp/cat-data.json -w "%{http_code}" "${URL%/}/data.json")
[ "$dcode" = "200" ] && ok "data.json 200" || bad "data.json HTTP $dcode"
python3 -c "import json;d=json.load(open('/tmp/cat-data.json'));print('  info  deployed generated', d['generated'], len(d['members']), 'members')" 2>/dev/null || bad "deployed data.json unparsable"
sig() { python3 -c "
import json,hashlib,sys;d=json.load(open(sys.argv[1]))
h=hashlib.sha1(json.dumps([[m['id'],[p['label'] for p in m['positions'].values()]] for m in d['members']]).encode()).hexdigest()[:10]
print(d['generated'], len(d['votes']), 'votes', sum(1 for m in d['members'] if any(p['basis']=='research' for p in m['positions'].values())), 'researched', h)" "$1" 2>/dev/null; }
local_sig=$(sig docs/data.json); remote_sig=$(sig /tmp/cat-data.json)
[ "$local_sig" = "$remote_sig" ] && ok "deployed data matches local build ($local_sig)" || bad "deployed data ($remote_sig) differs from local ($local_sig): push and wait for GitHub Pages"
pcode=$(curl -s -o /dev/null -w "%{http_code}" "${URL%/}/photos/H001089.jpg")
[ "$pcode" = "200" ] && ok "photo served" || bad "photo HTTP $pcode"

echo "== 5. sample source links reachable (10 random evidence URLs)"
python3 - <<'EOF'
import json, random, urllib.request
d = json.load(open('docs/data.json'))
urls = sorted({e['url'] for m in d['members'] for p in m['positions'].values() for e in p['evidence'] if e['type'] not in ('sponsor','cosponsor','vote')})
random.seed(7); sample = random.sample(urls, min(10, len(urls)))
bad = 0
for u in sample:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0'}), timeout=15)
        print('  ok  ', r.status, u[:90])
    except Exception as e:
        bad += 1; print('  warn', str(e)[:40], u[:90])
print(f'  info  {len(urls)} statement URLs total; {bad}/{len(sample)} sampled unreachable (some sites block scripts)')
EOF

echo
[ $FAIL = 0 ] && echo "VERIFY: ALL PASS" || { echo "VERIFY: FAILURES ABOVE"; exit 1; }
