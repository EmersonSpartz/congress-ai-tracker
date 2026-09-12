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
python3 - <<'EOF' || FAIL=1
import json, sys, collections, re
d = json.load(open('docs/data.json'))
ms = d['members']; errs = []
if not (530 <= len(ms) <= 541): errs.append(f'member count {len(ms)}')
sen = sum(1 for m in ms if m['chamber']=='Senate')
if sen != 100: errs.append(f'senators {sen}')
ids = collections.Counter(m['id'] for m in ms)
if any(v>1 for v in ids.values()): errs.append('duplicate ids')
dims = [x['key'] for x in d['dimensions']]
for m in ms:
    for k in dims:
        p = m['positions'].get(k)
        if not p: errs.append(f"{m['id']} missing {k}"); continue
        if p['score'] is not None and p['score'] not in (-2,-1,0,1,2): errs.append(f"{m['id']} bad score {k}")
        if p['score'] is not None and not p['evidence']: errs.append(f"{m['id']} {k} score without evidence")
        for e in p['evidence']:
            if not e.get('url','').startswith('http'): errs.append(f"{m['id']} {k} evidence without url")
    if not m['photo']: errs.append(f"{m['id']} no photo")
# em dashes anywhere in public text
txt = json.dumps(d, ensure_ascii=False)
n_em = txt.count('—')
if n_em: errs.append(f'{n_em} em dashes in data.json')
# key votes present
if not d['votes']: errs.append('no key votes')
for v in d['votes']:
    n = sum(1 for m in ms if v['id'] in m['votes'])
    if n < 90: errs.append(f"key vote {v['id']} only {n} member votes")
# researched share
researched = sum(1 for m in ms if any(p['basis']=='research' for p in m['positions'].values()))
print(f"  info  researched members: {researched}/{len(ms)}; bills: {len(d['bills'])}; votes: {len(d['votes'])}")
for e in errs[:15]: print('  FAIL ', e)
if errs: sys.exit(1)
print('  PASS  data.json integrity')
EOF

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
local_gen=$(python3 -c "import json;print(json.load(open('docs/data.json'))['generated'])")
remote_gen=$(python3 -c "import json;print(json.load(open('/tmp/cat-data.json'))['generated'])" 2>/dev/null)
[ "$local_gen" = "$remote_gen" ] && ok "deployed data matches local build ($local_gen)" || echo "  WARN  deployed data ($remote_gen) differs from local ($local_gen): deploy pending?"
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
