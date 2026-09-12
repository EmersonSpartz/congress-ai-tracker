#!/usr/bin/env python3
"""Build site/data.json for the Congress AI Tracker.

Inputs (all under source/):
  members.json              roster from unitedstates/congress-legislators (+ committees)
  member_records.json       per-member relevant bills + key votes (from official bulk data)
  bills_tech_candidates.json  bill index (govinfo BILLSTATUS) for the candidate bills
  bill_classifications.json   dimension / direction / plain-English per bill (agent-classified)
  votes_index.json          every downloaded roll call with per-member votes
  key_votes.json            which roll calls to feature, with plain-English framing
  research/*.json           per-member researched positions (agent output, verified)
  verification/*.json       fact-check verdicts per member
  landscape.json            caucuses, PACs, explainers (optional)
Output: site/data.json and site/photos/*.jpg
"""
import json, os, glob, re, shutil, collections, datetime, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'source')
SITE = os.path.join(ROOT, 'docs')

def load(name, default=None):
    p = os.path.join(SRC, name)
    if not os.path.exists(p):
        if default is not None:
            return default
        raise SystemExit(f'missing {p}')
    with open(p) as f:
        return json.load(f)

STATE_NAMES = {'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming','DC':'District of Columbia','PR':'Puerto Rico','GU':'Guam','VI':'U.S. Virgin Islands','AS':'American Samoa','MP':'Northern Mariana Islands'}

# Display dimensions and how bill lanes map onto them
DIMENSIONS = [
    {'key':'data_centers','label':'AI data centers','short':'Data centers',
     'question':'Should America build AI data centers as fast as possible, or slow down until electric bills, water and communities are protected?',
     'scale':{-2:'Pause or block',-1:'Protect ratepayers first',0:'Mixed',1:'Build, with conditions',2:'Build faster'},
     'lanes':['data_centers_energy']},
    {'key':'ai_risk','label':'AI risk and control','short':'AI risk',
     'question':'How dangerous is advanced AI, and how hard should the government regulate the companies building it?',
     'scale':{-2:'Strict rules now',-1:'Targeted guardrails',0:'Mixed',1:'Light touch',2:'Hands off'},
     'lanes':['ai_risk_control','deepfakes_likeness_copyright','workers_jobs']},
    {'key':'tech_regulation','label':'Big Tech regulation','short':'Tech rules',
     'question':'Should Washington rein in the big technology companies (kids safety, privacy, antitrust, Section 230), or leave them mostly alone?',
     'scale':{-2:'Rein in Big Tech',-1:'Targeted rules',0:'Mixed',1:'Light touch',2:'Hands off'},
     'lanes':['tech_regulation_broad','kids_online_safety']},
    {'key':'preemption','label':'State AI laws','short':'State laws',
     'question':'Should states be allowed to pass their own AI laws, or should one national rule block them?',
     'scale':{-2:'Let states regulate',-1:'Leans states',0:'Mixed or conditional',1:'Leans national rule',2:'One national rule'},
     'lanes':['preemption_state_laws']},
    {'key':'china_chips','label':'China and AI chips','short':'Chips',
     'question':'Should the U.S. keep its most advanced AI chips away from China, or sell more of them abroad?',
     'scale':{-2:'Tighten export controls',-1:'Leans hawkish',0:'Mixed',1:'Leans sell more',2:'Sell more chips abroad'},
     'lanes':['chips_china_export']},
]
LANE_TO_DIM = {lane: d['key'] for d in DIMENSIONS for lane in d['lanes']}
SIG_W = {'major':3,'notable':2,'minor':1}

def bill_url(b):
    typ = {'HR':'house-bill','S':'senate-bill','HJRES':'house-joint-resolution','SJRES':'senate-joint-resolution','HRES':'house-resolution','SRES':'senate-resolution','HCONRES':'house-concurrent-resolution','SCONRES':'senate-concurrent-resolution'}[b['type']]
    cong = {118:'118th',119:'119th'}[b['congress']]
    return f"https://www.congress.gov/bill/{cong}-congress/{typ}/{b['number']}"

def bill_label(b):
    t = {'HR':'H.R.','S':'S.','HJRES':'H.J.Res.','SJRES':'S.J.Res.','HRES':'H.Res.','SRES':'S.Res.','HCONRES':'H.Con.Res.','SCONRES':'S.Con.Res.'}[b['type']]
    return f"{t}{b['number']}"

def clean(s):
    if s is None: return s
    return s.replace('—', ', ').replace(' , ', ', ').replace('--', ', ')

def main():
    members = load('members.json')
    records = load('member_records.json')
    bills_idx = load('bills_tech_candidates.json')
    cls = load('bill_classifications.json')
    votes_idx = load('votes_index.json', {})
    key_votes = load('key_votes.json', [])
    landscape = load('landscape.json', {})
    ls_pacs = landscape.get('member_pacs', {})
    ls_groups = landscape.get('member_groups', {})
    ls_letters = landscape.get('member_letters', {})
    LETTER_SCORE = {('preemption','more_guardrails'): -2, ('preemption','fewer_rules'): 2, ('preemption','mixed_or_neutral'): 0}
    research = {}
    for p in glob.glob(os.path.join(SRC, 'research', '*.json')):
        with open(p) as f:
            for m in json.load(f):
                research[m['bioguide']] = m
    verification = {}
    for p in glob.glob(os.path.join(SRC, 'verification', '*.json')):
        with open(p) as f:
            for v in json.load(f):
                verification[v['bioguide']] = v

    # ---- bills used by the site
    rel = {k: v for k, v in cls.items() if v.get('relevant') and v.get('dimension') != 'not_relevant'}
    bills_out = {}
    for bid, c in rel.items():
        b = bills_idx[bid]
        bills_out[bid] = {
            'id': bid, 'label': bill_label(b), 'congress': b['congress'], 'title': clean(b['title']),
            'lane': c['dimension'], 'dim': LANE_TO_DIM.get(c['dimension']), 'direction': c['direction'],
            'significance': c['significance'], 'what': clean(c['plain_english']), 'url': bill_url(b),
            'introduced': b['introduced'], 'sponsor': b['sponsor'][0][1] if b['sponsor'] else None,
            'n_cosponsors': len(b['cosponsors']), 'latest_action': b['latest_action'], 'latest_action_date': b['latest_action_date'],
            'enacted': bool(b['laws']),
        }

    # ---- key votes
    votes_out = []
    for kv in key_votes:
        v = votes_idx.get(kv['id'])
        if not v:
            print('WARNING key vote missing from index:', kv['id'], file=sys.stderr)
            continue
        votes_out.append({**kv, 'chamber': v['chamber'], 'date': v['date'], 'tally': v['tally'], 'govtrack': v['govtrack'], 'official': v.get('url') or kv.get('official')})
    kv_ids = [k['id'] for k in votes_out]

    # ---- members
    out_members = []
    for m in members:
        rec = records[m['bioguide']]
        r = research.get(m['bioguide'])
        ver = verification.get(m['bioguide'], {})
        verdicts = {c['url']: c for c in ver.get('checks', [])}
        # bills grouped by display dimension
        mbills = []
        for it in rec['bills']:
            bo = bills_out.get(it['bill'])
            if not bo: continue
            mbills.append({'id': it['bill'], 'role': it['role'], 'date': it['date']})
        by_dim_signal = collections.defaultdict(lambda: {'guard':0,'hands':0,'n':0,'examples':[]})
        for it in mbills:
            bo = bills_out[it['id']]
            if not bo['dim']: continue
            w = SIG_W[bo['significance']] * (2 if it['role']=='sponsor' else 1)
            s = by_dim_signal[bo['dim']]
            s['n'] += 1
            if bo['direction'] == 'more_guardrails': s['guard'] += w
            elif bo['direction'] == 'fewer_rules': s['hands'] += w
            s['examples'].append(it['id'])
        positions = {}
        n_statements = 0
        for d in DIMENSIONS:
            key = d['key']
            rp = (r or {}).get('positions', {}).get(key)
            evidence = []
            score = None; conf = 'none'; summary = None; basis = 'none'
            if rp:
                for e in rp.get('evidence', []):
                    e = dict(e)
                    e['title'] = clean(e.get('title')); e['what_it_shows'] = clean(e.get('what_it_shows'))
                    vd = verdicts.get(e.get('url'))
                    if e['type'] in ('sponsor','cosponsor','vote'):
                        e['verified'] = 'record'
                    elif vd:
                        e['verified'] = vd['verdict']
                        if vd.get('corrected_quote'): e['quote'] = vd['corrected_quote']
                        if vd.get('corrected_date'): e['date'] = vd['corrected_date']
                    else:
                        e['verified'] = 'unchecked'
                    if e['verified'] in ('unsupported','wrong_person'):
                        continue
                    evidence.append(e)
                statements = [e for e in evidence if e['type'] not in ('sponsor','cosponsor','vote')]
                n_statements += len(statements)
                score = rp.get('score'); conf = rp.get('confidence','low'); summary = clean(rp.get('summary'))
                basis = 'research'
                if score is not None and not evidence:
                    score = None; conf = 'none'; basis = 'none'
                    summary = 'The sources we found for this could not be verified, so no position is shown.'
                elif score is not None and not statements and conf == 'high':
                    conf = 'medium'
            n_statements += len([l for l in ls_letters.get(m['bioguide'], []) if l['dim'] == key])
            sig = by_dim_signal.get(key)
            if score is None and sig and sig['n'] > 0:
                net = sig['guard'] - sig['hands']
                if net >= 3: score = -1
                elif net <= -3: score = 1
                else: score = 0
                conf = 'low'; basis = 'record'
                ex = [bills_out[i]['label'] + ' (' + (bills_out[i]['title'] or '')[:60] + ')' for i in sig['examples'][:2]]
                verb = 'sponsored or cosponsored'
                summary = f"No public statements found. Record only: {verb} {sig['n']} related bill{'s' if sig['n']!=1 else ''}, including {'; '.join(ex)}."
                for i in sig['examples'][:6]:
                    bo = bills_out[i]
                    role = next((it['role'] for it in mbills if it['id']==i), 'cosponsor')
                    evidence.append({'type': role, 'date': None, 'title': f"{'Sponsored' if role=='sponsor' else 'Cosponsored'} {bo['label']}: {bo['title']}", 'url': bo['url'], 'quote': None, 'what_it_shows': bo['what'], 'verified': 'record'})
            # signed letters and public statements collected in the landscape pass
            my_letters = [l for l in ls_letters.get(m['bioguide'], []) if l['dim'] == key]
            seen_urls = {e.get('url') for e in evidence}
            for l in my_letters:
                if l['url'] in seen_urls: continue
                evidence.append({'type': l['type'], 'date': l.get('date'), 'title': clean(l['title']), 'url': l['url'], 'quote': None, 'what_it_shows': clean(l['what']), 'verified': 'landscape'})
                seen_urls.add(l['url'])
            if my_letters and (score is None or basis == 'record'):
                dirs = collections.Counter(l['direction'] for l in my_letters)
                d0 = dirs.most_common(1)[0][0]
                if len(dirs) == 1 or dirs[d0] >= 2 * sum(v for k2, v in dirs.items() if k2 != d0):
                    ls = LETTER_SCORE.get((key, d0))
                    if ls is None:
                        ls = {'more_guardrails': -1, 'fewer_rules': 1, 'mixed_or_neutral': 0}[d0]
                    score = ls; conf = 'medium'; basis = 'letter'
                    lt = my_letters[0]
                    summary = f"No detailed statements collected yet, but {'signed' if lt['type']=='letter' else 'made'} {'a letter' if lt['type']=='letter' else 'a public statement'}: {clean(lt['title'])[:140]}." + (f" Plus {len(my_letters)-1} more." if len(my_letters) > 1 else '')
            if score is None and summary is None:
                summary = 'No public position found.'
            positions[key] = {'score': score, 'label': d['scale'][score] if score is not None else 'No public position found', 'confidence': conf, 'basis': basis, 'summary': summary, 'evidence': evidence}
        # key votes
        mv = {}
        for kid in kv_ids:
            v = votes_idx[kid]['votes'].get(m['bioguide'])
            if v: mv[kid] = v
        # activity
        n119 = sum(1 for it in mbills if it['id'].startswith('119'))
        nspon = sum(1 for it in mbills if it['role']=='sponsor' and it['id'].startswith('119'))
        n_ai = sum(1 for it in mbills if bills_out[it['id']]['lane'] in ('ai_risk_control','data_centers_energy','preemption_state_laws','deepfakes_likeness_copyright','ai_government_research','workers_jobs','chips_china_export'))
        groups = list((r or {}).get('groups', []))
        for g in ls_groups.get(m['bioguide'], []):
            if not any(g.lower()[:30] in x.lower() or x.lower()[:30] in g.lower() for x in groups):
                groups.append(g)
        pacs = ls_pacs.get(m['bioguide'], [])
        for p_ in pacs:
            for key_ in ('detail','agenda'): p_[key_] = clean(p_.get(key_))
        leader_role = any(re.search(r'\b(chair|ranking member|co-chair|vice-chair|lead sponsor|author|negotiator)\b', g, re.I) for g in groups)
        if nspon >= 3 or (leader_role and (nspon >= 1 or n_statements >= 4)) or n_statements >= 8:
            level = 'Leader'
        elif n119 >= 8 or n_statements >= 3 or nspon >= 1:
            level = 'Active'
        elif n119 >= 1 or n_statements >= 1:
            level = 'Some'
        else:
            level = 'Quiet'
        photo = f"photos/{m['bioguide']}.jpg" if os.path.exists(os.path.join(SRC, 'photos', m['bioguide'] + '.jpg')) else None
        party = {'Democrat':'D','Republican':'R','Independent':'I'}.get(m['party'], m['party'][:1])
        out_members.append({
            'id': m['bioguide'], 'name': m['name'], 'first': m['first'], 'last': m['last'], 'party': party,
            'state': m['state'], 'state_name': STATE_NAMES.get(m['state'], m['state']), 'district': m['district'], 'chamber': m['chamber'],
            'url': m['url'], 'wikipedia': m['wikipedia'], 'photo': photo, 'first_term': m['first_term_start'][:4],
            'committees': [c['name'] for c in m['committees']],
            'groups': groups,
            'activity': {'level': level, 'n_bills_119': n119, 'n_sponsored_119': nspon, 'n_ai_bills': n_ai, 'n_statements': n_statements},
            'positions': positions, 'votes': mv, 'bills': mbills, 'pacs': pacs,
            'signature': clean((r or {}).get('signature')) or None,
            'quote': (r or {}).get('notable_quote'),
        })
    # drop a quote that failed verification
    for om in out_members:
        q = om.get('quote')
        if q:
            vd = verification.get(om['id'], {}).get('checks', [])
            bad = [c for c in vd if c['url'] == q.get('url') and c['verdict'] in ('unsupported','wrong_person')]
            if bad: om['quote'] = None
            else:
                fix = [c for c in vd if c['url'] == q.get('url') and c.get('corrected_quote')]
                if fix: q['text'] = fix[0]['corrected_quote']
                q['text'] = clean(q['text'])

    # ---- stats
    stats = {'members': len(out_members), 'senate': sum(1 for x in out_members if x['chamber']=='Senate'), 'house': sum(1 for x in out_members if x['chamber']=='House')}
    for d in DIMENSIONS:
        c = collections.Counter()
        for x in out_members:
            c[str(x['positions'][d['key']]['score'])] += 1
        stats[d['key']] = dict(c)
    stats['activity'] = dict(collections.Counter(x['activity']['level'] for x in out_members))
    stats['basis'] = dict(collections.Counter(p['basis'] for x in out_members for p in x['positions'].values()))
    stats['pac_members'] = sum(1 for x in out_members if x['pacs'])

    os.makedirs(SITE, exist_ok=True)
    os.makedirs(os.path.join(SITE, 'photos'), exist_ok=True)
    for p in glob.glob(os.path.join(SRC, 'photos', '*.jpg')):
        dst = os.path.join(SITE, 'photos', os.path.basename(p))
        if not os.path.exists(dst) or os.path.getmtime(p) > os.path.getmtime(dst):
            shutil.copy2(p, dst)
    data = {
        'generated': datetime.date.today().isoformat(), 'congress': 119,
        'dimensions': [{k: v for k, v in d.items() if k != 'lanes'} | {'scale': {str(k): v for k, v in d['scale'].items()}} for d in DIMENSIONS],
        'votes': votes_out, 'bills': bills_out, 'members': out_members, 'stats': stats,
        'landscape': {'explainers': landscape.get('explainers', {})},
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(SITE, 'data.json'), 'w') as f:
        f.write(payload)
    import hashlib
    stamp = hashlib.sha1(payload.encode('utf-8')).hexdigest()[:10]
    js_path = os.path.join(SITE, 'app.js')
    js = open(js_path).read()
    js = re.sub(r"data\.json\?v=[A-Za-z0-9_]+", f"data.json?v={stamp}", js)
    open(js_path, 'w').write(js)
    idx_path = os.path.join(SITE, 'index.html')
    idx = open(idx_path).read()
    idx = re.sub(r'app\.js(\?v=[A-Za-z0-9_]+)?', f'app.js?v={stamp}', idx)
    idx = re.sub(r'styles\.css(\?v=[A-Za-z0-9_]+)?', f'styles.css?v={stamp}', idx)
    open(idx_path, 'w').write(idx)
    print('build stamp', stamp)
    print(f"wrote docs/data.json: {len(out_members)} members, {len(bills_out)} bills, {len(votes_out)} key votes, {len(research)} researched, {len(verification)} verified")
    print('stats', json.dumps(stats))

if __name__ == '__main__':
    main()
