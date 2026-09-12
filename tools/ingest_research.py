#!/usr/bin/env python3
"""Turn research-workflow output into source/research/*.json and source/verification/*.json.

Usage: python3 tools/ingest_research.py <workflow_output_or_journal> [...]
Accepts either the task output JSON ({"result": {"groups": [...]}}) or a workflow journal.jsonl
(one {"type":"result", ...} line per agent; research results have {members:[...]}, verification results
have {bioguide, checks, score_objections}). Files are named by group so re-ingesting overwrites cleanly.
"""
import json, os, sys, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES_DIR = os.path.join(ROOT, 'source', 'research')
VER_DIR = os.path.join(ROOT, 'source', 'verification')
os.makedirs(RES_DIR, exist_ok=True); os.makedirs(VER_DIR, exist_ok=True)

def write_group(tag, members, verifications):
    tag = re.sub(r'[^A-Za-z0-9_-]', '_', tag)
    if members:
        json.dump(members, open(os.path.join(RES_DIR, f'{tag}.json'), 'w'), ensure_ascii=False, indent=0)
    vs = [v for v in verifications if v and v.get('bioguide')]
    if vs:
        json.dump(vs, open(os.path.join(VER_DIR, f'{tag}.json'), 'w'), ensure_ascii=False, indent=0)
    return len(members or []), len(vs)

n_m = n_v = 0
for path in sys.argv[1:]:
    if path.endswith('.jsonl'):
        # journal: pair research results with verification results by member bioguide
        lab = {}; members = []; ver = []
        for line in open(path):
            try: d = json.loads(line)
            except Exception: continue
            if d.get('type') == 'started': lab[d['agentId']] = d.get('label', '')
            if d.get('type') == 'result':
                r = d.get('result'); L = lab.get(d.get('agentId'), '')
                if isinstance(r, dict) and isinstance(r.get('members'), list):
                    for m in r['members']: m['_group'] = L.replace('research:', '')
                    members += r['members']
                elif isinstance(r, dict) and r.get('bioguide') and 'checks' in r:
                    ver.append(r)
        by_group = collections.defaultdict(list)
        for m in members: by_group[m.pop('_group', 'journal')].append(m)
        vmap = {v['bioguide']: v for v in ver}
        for g, ms in by_group.items():
            a, b = write_group(g, ms, [vmap[m['bioguide']] for m in ms if m.get('bioguide') in vmap])
            n_m += a; n_v += b
    else:
        d = json.load(open(path))
        result = d.get('result', d)
        for g in result.get('groups', []):
            if not g: continue
            a, b = write_group(g.get('group', 'group'), g.get('members', []), g.get('verification', []))
            n_m += a; n_v += b
        if result.get('failed'):
            print('failed groups:', result['failed'])
print(f'ingested {n_m} members, {n_v} verifications -> {RES_DIR}, {VER_DIR}')
