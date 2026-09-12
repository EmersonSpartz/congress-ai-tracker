#!/usr/bin/env python3
"""Build docs/data.json for the Congress AI Tracker.

Inputs (all under source/):
  members.json              roster from unitedstates/congress-legislators (+ committees)
  member_records.json       per-member relevant bills + key votes (from official bulk data)
  bills_tech_candidates.json  bill index (govinfo BILLSTATUS) for the candidate bills
  bill_classifications.json   dimension / direction / plain-English per bill (agent-classified)
  votes_index.json          every downloaded roll call with per-member votes
  key_votes.json            which roll calls to feature, with plain-English framing
  landscape.json            explainers, per-member PACs, caucuses, signed letters (tools/make_landscape.py)
  research/*.json           per-member researched positions (agent output)
  verification/*.json       fact-check verdicts per member
Output: docs/data.json, docs/photos/*.jpg, and a build stamp written into docs/app.js and docs/index.html.
"""
import json, os, glob, re, shutil, collections, datetime, sys, hashlib, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'source')
SITE = os.path.join(ROOT, 'docs')
WARN = []

def warn(msg):
    WARN.append(msg)

def load(name, default=None):
    p = os.path.join(SRC, name)
    if not os.path.exists(p):
        if default is not None:
            return default
        raise SystemExit(f'missing {p}')
    with open(p) as f:
        return json.load(f)

STATE_NAMES = {'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming','DC':'District of Columbia','PR':'Puerto Rico','GU':'Guam','VI':'U.S. Virgin Islands','AS':'American Samoa','MP':'Northern Mariana Islands'}

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
DIM_KEYS = [d['key'] for d in DIMENSIONS]
LANE_TO_DIM = {lane: d['key'] for d in DIMENSIONS for lane in d['lanes']}
SIG_W = {'major':3,'notable':2,'minor':1}
EVIDENCE_TYPES = {'vote','sponsor','cosponsor','letter','statement','hearing','interview','op_ed','social_post','pac','other'}
VERDICTS = {'confirmed','partially_supported','unsupported','unreachable','wrong_person'}
DIRECTIONS = {'more_guardrails','fewer_rules','mixed_or_neutral'}
BILL_TYPE_URL = {'HR':'house-bill','S':'senate-bill','HJRES':'house-joint-resolution','SJRES':'senate-joint-resolution','HRES':'house-resolution','SRES':'senate-resolution','HCONRES':'house-concurrent-resolution','SCONRES':'senate-concurrent-resolution'}
BILL_TYPE_LABEL = {'HR':'H.R.','S':'S.','HJRES':'H.J.Res.','SJRES':'S.J.Res.','HRES':'H.Res.','SRES':'S.Res.','HCONRES':'H.Con.Res.','SCONRES':'S.Con.Res.'}

def bill_url(b):
    return f"https://www.congress.gov/bill/{b['congress']}th-congress/{BILL_TYPE_URL[b['type']]}/{b['number']}"

def bill_label(b):
    return f"{BILL_TYPE_LABEL[b['type']]}{b['number']}"

def clean(s):
    """Public copy has no em dashes. Between words an em dash becomes a hyphen (America-Israel); otherwise a comma."""
    if s is None: return s
    if not isinstance(s, str): s = str(s)
    s = re.sub(r'(?<=\w)—(?=\w)', '-', s)
    s = s.replace(' — ', ', ').replace('—', ', ').replace(' , ', ', ').replace('--', ', ')
    return s

def safe_url(u):
    if not isinstance(u, str): return None
    u = u.strip()
    return u if re.match(r'^https?://[^\s<>"\']+$', u) else None

def norm_url(u):
    if not isinstance(u, str): return ''
    u = u.strip().lower()
    u = re.sub(r'^https?://(www\.)?', '', u)
    u = u.split('#')[0]
    u = re.sub(r'[?&]utm_[^&]*', '', u)
    return u.rstrip('/').rstrip('?')

def norm_date(d):
    """Return YYYY-MM-DD, YYYY-MM or None from the many date shapes in the inputs."""
    if not d or not isinstance(d, str): return None
    d = d.strip()
    m = re.match(r'^(\d{4})-(\d{2})(?:-(\d{2}))?', d)
    if m: return d[:10] if m.group(3) else d[:7]
    m = re.match(r'^(\d{1,2})-([A-Za-z]{3})-(\d{4})$', d)  # 22-May-2025 (House Clerk)
    if m:
        try: return datetime.datetime.strptime(d, '%d-%b-%Y').strftime('%Y-%m-%d')
        except ValueError: return None
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%d %b %Y', '%m/%d/%Y', '%B %Y', '%b %Y'):
        try: return datetime.datetime.strptime(d, fmt).strftime('%Y-%m-%d' if '%d' in fmt else '%Y-%m')
        except ValueError: pass
    return d if re.match(r'^\d{4}$', d) else None

def norm_name(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z]', '', s)

def coerce_score(v):
    if v is None: return None
    try:
        iv = int(str(v).strip())
    except (ValueError, TypeError):
        return None
    return iv if -2 <= iv <= 2 else None

def validate_member(r, roster, src):
    """Normalize one research entry; return None (and warn) if it cannot be trusted."""
    if not isinstance(r, dict) or not r.get('bioguide'):
        warn(f'{src}: research entry without bioguide skipped: {str(r)[:80]}'); return None
    bg = str(r['bioguide']).strip()
    m = roster.get(bg)
    if not m:
        warn(f'{src}: research bioguide {bg} not in roster; skipped'); return None
    rn = norm_name(r.get('name') or '')
    if rn and norm_name(m['last']) not in rn and norm_name(m['name']) != rn:
        warn(f"{src}: research name '{r.get('name')}' does not match roster {m['name']} ({bg}); skipped"); return None
    pos = r.get('positions') if isinstance(r.get('positions'), dict) else {}
    out_pos = {}
    for k in DIM_KEYS:
        p = pos.get(k)
        if not isinstance(p, dict): p = {}
        ev_in = p.get('evidence') if isinstance(p.get('evidence'), list) else []
        ev = []
        for e in ev_in:
            if isinstance(e, str): e = {'type': 'other', 'title': 'Source', 'url': e}
            if not isinstance(e, dict): continue
            url = safe_url(e.get('url'))
            if not url: continue
            typ = e.get('type') if e.get('type') in EVIDENCE_TYPES else 'other'
            quote = e.get('quote') if isinstance(e.get('quote'), str) and e.get('quote').strip() else None
            if quote and len(quote.split()) > 60: quote = ' '.join(quote.split()[:60]) + '...'
            ev.append({'type': typ, 'date': norm_date(e.get('date')), 'title': clean(str(e.get('title') or 'Source'))[:200], 'url': url, 'quote': quote, 'what_it_shows': clean(str(e.get('what_it_shows') or ''))[:400]})
        score = coerce_score(p.get('score'))
        if p.get('score') is not None and score is None:
            warn(f"{bg} {k}: bad score {p.get('score')!r} treated as null")
        conf = p.get('confidence') if p.get('confidence') in ('high','medium','low','none') else ('low' if score is not None else 'none')
        out_pos[k] = {'score': score, 'confidence': conf, 'summary': clean(str(p.get('summary') or ''))[:700], 'evidence': ev}
    q = r.get('notable_quote')
    quote = None
    if isinstance(q, dict) and isinstance(q.get('text'), str) and q['text'].strip() and safe_url(q.get('url')):
        quote = {'text': clean(q['text'].strip())[:400], 'date': norm_date(q.get('date')), 'url': safe_url(q['url'])}
    groups = [clean(str(g))[:90] for g in (r.get('groups') or []) if isinstance(g, str) and g.strip() and not re.search(r'endors|super pac|\bpac\b|leading the future|public first', g, re.I)] if isinstance(r.get('groups'), list) else []
    sig = r.get('signature') if isinstance(r.get('signature'), str) else None
    if sig and re.match(r'^\s*no notable', sig, re.I): sig = None
    return {'bioguide': bg, 'positions': out_pos, 'signature': clean(sig)[:300] if sig else None, 'quote': quote, 'groups': groups}

def load_research_files(subdir, roster, is_verification=False):
    out = {}
    for p in sorted(glob.glob(os.path.join(SRC, subdir, '*.json'))):
        src = os.path.basename(p)
        try:
            with open(p) as f: data = json.load(f)
        except Exception as e:
            warn(f'{src}: unreadable ({e})'); continue
        if isinstance(data, dict):
            data = data.get('members') or data.get('checks') if isinstance(data.get('members') or data.get('checks'), list) else ([data] if 'bioguide' in data else list(data.values()))
        if not isinstance(data, list):
            warn(f'{src}: unexpected shape'); continue
        for r in data:
            if is_verification:
                if not isinstance(r, dict) or not r.get('bioguide'): continue
                bg = str(r['bioguide']).strip()
                if bg not in roster:
                    warn(f'{src}: verification for unknown bioguide {bg} skipped'); continue
                checks = []
                for c in (r.get('checks') or []):
                    if not isinstance(c, dict) or not isinstance(c.get('url'), str): continue
                    checks.append({'url': c['url'], 'verdict': c.get('verdict') if c.get('verdict') in VERDICTS else 'unchecked',
                                   'corrected_quote': c.get('corrected_quote') if isinstance(c.get('corrected_quote'), str) and c.get('corrected_quote').strip() else None,
                                   'corrected_date': norm_date(c.get('corrected_date')), 'note': str(c.get('note') or '')[:300]})
                objections = [o for o in (r.get('score_objections') or []) if isinstance(o, dict) and o.get('dimension') in DIM_KEYS]
                if bg in out:
                    out[bg]['checks'] += checks; out[bg]['score_objections'] += objections
                else:
                    out[bg] = {'bioguide': bg, 'checks': checks, 'score_objections': objections}
            else:
                v = validate_member(r, roster, src)
                if not v: continue
                if v['bioguide'] in out: warn(f"{src}: duplicate research for {v['bioguide']}; later file wins")
                out[v['bioguide']] = v
    return out

def main():
    members = load('members.json')
    roster = {m['bioguide']: m for m in members}
    records = load('member_records.json')
    bills_idx = load('bills_tech_candidates.json')
    cls = load('bill_classifications.json')
    votes_idx = load('votes_index.json', {})
    key_votes = load('key_votes.json', [])
    landscape = load('landscape.json', {})
    ls_pacs = landscape.get('member_pacs', {})
    ls_groups = landscape.get('member_groups', {})
    ls_letters = landscape.get('member_letters', {})
    research = load_research_files('research', roster)
    verification = load_research_files('verification', roster, is_verification=True)

    # ---- bills used by the site
    rel = {k: v for k, v in cls.items() if v.get('relevant') and v.get('dimension') != 'not_relevant'}
    bills_out = {}
    for bid, c in rel.items():
        b = bills_idx[bid]
        bills_out[bid] = {
            'id': bid, 'label': bill_label(b), 'congress': b['congress'], 'title': clean(b['title']),
            'lane': c['dimension'], 'dim': LANE_TO_DIM.get(c['dimension']),
            'direction': c['direction'] if c['direction'] in DIRECTIONS else 'mixed_or_neutral',
            'significance': c['significance'] if c['significance'] in SIG_W else 'minor', 'what': clean(c['plain_english']), 'url': bill_url(b),
            'introduced': b['introduced'], 'sponsor': b['sponsor'][0][1] if b['sponsor'] else None,
            'n_cosponsors': len(b['cosponsors']), 'latest_action': clean(b['latest_action']), 'latest_action_date': b['latest_action_date'],
            'enacted': bool(b['laws']),
        }
    inv_type = {v: k for k, v in BILL_TYPE_URL.items()}
    def bill_id_from_url(u):
        m = re.search(r'congress\.gov/bill/(\d+)th-congress/([a-z-]+)/(\d+)', u or '', re.I)
        if not m: return None
        t = inv_type.get(m.group(2).lower())
        return f"{m.group(1)}-{t}{m.group(3)}" if t else None

    # ---- key votes
    votes_out = []
    for kv in key_votes:
        v = votes_idx.get(kv['id'])
        if not v:
            warn(f"key vote missing from index: {kv['id']}"); continue
        votes_out.append({**kv, 'plain': clean(kv.get('plain')), 'title': clean(kv.get('title')), 'chamber': v['chamber'], 'date': norm_date(v['date']) or v['date'], 'tally': v['tally'], 'govtrack': v['govtrack'], 'official': v.get('url') or kv.get('official')})
    kv_ids = [k['id'] for k in votes_out]

    LETTER_SCORE = {('preemption','more_guardrails'): -2, ('preemption','fewer_rules'): 2, ('preemption','mixed_or_neutral'): 0}
    out_members = []
    n_dropped_evidence = 0
    for m in members:
        rec = records[m['bioguide']]
        r = research.get(m['bioguide'])
        ver = verification.get(m['bioguide'], {})
        verdicts = {norm_url(c['url']): c for c in ver.get('checks', [])}
        used_verdicts = set()
        objections = {o['dimension']: o for o in ver.get('score_objections', [])}
        # official record: bills
        mbills = [{'id': it['bill'], 'role': it['role'], 'date': it['date']} for it in rec['bills'] if it['bill'] in bills_out]
        my_bill_roles = {(it['id'], it['role']) for it in mbills}
        role_of = {it['id']: it['role'] for it in mbills}
        by_dim_signal = collections.defaultdict(lambda: {'guard':0,'hands':0,'neutral':0,'n':0,'examples':[]})
        for it in mbills:
            bo = bills_out[it['id']]
            if not bo['dim']: continue
            w = SIG_W[bo['significance']] * (2 if it['role']=='sponsor' else 1)
            s = by_dim_signal[bo['dim']]
            s['n'] += 1
            if bo['direction'] == 'more_guardrails': s['guard'] += w
            elif bo['direction'] == 'fewer_rules': s['hands'] += w
            else: s['neutral'] += w
            s['examples'].append((w, it['id'], it['role']))
        # official record: key votes
        mv = {kid: votes_idx[kid]['votes'][m['bioguide']] for kid in kv_ids if m['bioguide'] in votes_idx[kid]['votes']}

        positions = {}
        n_statements = 0
        for d in DIMENSIONS:
            key = d['key']
            rp = (r or {}).get('positions', {}).get(key)
            evidence = []
            score = None; conf = 'none'; summary = None; basis = 'none'
            research_statements = []
            if rp:
                dropped_here = 0
                for e in rp['evidence']:
                    e = dict(e)
                    if e['type'] in ('sponsor','cosponsor') and not bill_id_from_url(e['url']):
                        e['type'] = 'statement'   # a press release about a bill is a statement, checked like one
                    if e['type'] == 'vote' and not re.search(r'govtrack\.us/congress/votes/', e['url']):
                        e['type'] = 'statement'
                    if e['type'] in ('sponsor','cosponsor'):
                        bid = bill_id_from_url(e['url'])
                        if not bid or bid not in role_of:
                            warn(f"{m['bioguide']} {key}: claimed {e['type']} of {bid or e['url']} not in official record; dropped"); n_dropped_evidence += 1; continue
                        if (bid, e['type']) not in my_bill_roles:
                            e['type'] = role_of[bid]  # right bill, wrong role: use the official role
                        e['verified'] = 'record'
                    elif e['type'] == 'vote':
                        mm = re.search(r'/votes/\d+-(\d{4})/([hs])(\d+)', e['url'])
                        vid = f"{mm.group(2)}{mm.group(1)}-{int(mm.group(3))}" if mm else None
                        if not vid or vid not in mv:
                            warn(f"{m['bioguide']} {key}: claimed vote {e['url']} not in this member's record; dropped"); n_dropped_evidence += 1; continue
                        e['verified'] = 'record'
                        e['what_it_shows'] = ((e.get('what_it_shows') or '') + f" Recorded vote: {mv[vid]}.").strip()
                    else:
                        vd = verdicts.get(norm_url(e['url']))
                        if vd:
                            used_verdicts.add(norm_url(e['url']))
                            e['verified'] = vd['verdict']
                            if vd.get('corrected_quote'): e['quote'] = clean(vd['corrected_quote'])[:400]
                            if vd.get('corrected_date'): e['date'] = vd['corrected_date']
                        else:
                            e['verified'] = 'unchecked'
                        if e['verified'] in ('unsupported','wrong_person'):
                            dropped_here += 1; n_dropped_evidence += 1; continue
                        research_statements.append(e)
                    evidence.append(e)
                n_statements += len(research_statements)
                score = rp['score']; conf = rp['confidence']; summary = rp['summary'] or None
                basis = 'research'
                if score is not None and not evidence:
                    score = None; conf = 'none'
                    summary = 'The sources found for this could not be verified, so no position is shown.'
                elif score is not None:
                    if not research_statements and conf == 'high': conf = 'medium'
                    if dropped_here and conf == 'high': conf = 'medium'
                    if research_statements and all(e['verified'] in ('partially_supported','unreachable') for e in research_statements): conf = 'low'
                    obj = objections.get(key)
                    if obj:
                        sug = coerce_score(obj.get('suggested_score')) if obj.get('suggested_score') is not None else None
                        lab = (obj.get('suggested_label') or '').strip().lower()
                        lab_score = next((sc for sc, name in d['scale'].items() if name.lower() == lab), None)
                        if lab_score is not None: sug = lab_score          # the label is authoritative over the number (sign mistakes)
                        elif sug is not None and lab: sug = None           # number without a recognisable label: do not trust it
                        if sug is not None and sug != score:
                            score = sug
                            if conf == 'high': conf = 'medium'
                            summary = (summary or '').rstrip('.') + f". A fact-checker adjusted this reading: {clean(str(obj.get('objection') or ''))[:220]}"
                        elif obj.get('objection'):
                            if conf in ('high','medium'): conf = 'low'
            # signed letters and public statements from the landscape pass
            my_letters = [l for l in ls_letters.get(m['bioguide'], []) if l['dim'] == key and safe_url(l.get('url'))]
            seen_urls = {norm_url(e.get('url')) for e in evidence}
            scoring_letters = []
            for l in my_letters:
                if norm_url(l['url']) not in seen_urls:
                    evidence.append({'type': l['type'], 'date': norm_date(l.get('date')), 'title': clean(l['title'])[:200], 'url': l['url'], 'quote': None, 'what_it_shows': clean(l['what'])[:400], 'verified': 'landscape'})
                    seen_urls.add(norm_url(l['url']))
                    n_statements += 1
                # a joint statement by several speakers carries one direction for all of them: evidence only, never a score
                if l['type'] == 'letter' or l.get('n_signers', 1) <= 1:
                    scoring_letters.append(l)
            research_has_statements = bool(research_statements)
            if scoring_letters and score is None and not research_has_statements:
                dirs = collections.Counter(l['direction'] for l in scoring_letters)
                d0, n0 = dirs.most_common(1)[0]
                rest = sum(v for k2, v in dirs.items() if k2 != d0)
                if rest == 0 or n0 >= 2 * rest:
                    ls = LETTER_SCORE.get((key, d0))
                    if ls is None: ls = {'more_guardrails': -1, 'fewer_rules': 1, 'mixed_or_neutral': 0}[d0]
                    score = ls; conf = 'medium'; basis = 'letter'
                    lt = next(l for l in scoring_letters if l['direction'] == d0)
                    verb = 'Signed a letter' if lt['type'] == 'letter' else 'Made a public statement'
                    summary = f"{verb}: {clean(lt['title'])[:150]}." + (f" Plus {len(my_letters)-1} more item{'s' if len(my_letters)-1 != 1 else ''} below." if len(my_letters) > 1 else '')
            # bill record fallback
            sig = by_dim_signal.get(key)
            if score is None and not research_has_statements and sig and sig['n'] > 0:
                if sig['guard'] and not sig['hands']: score = -1
                elif sig['hands'] and not sig['guard']: score = 1
                elif sig['guard'] and sig['hands']: score = 0
                if score is not None:
                    conf = 'low'; basis = 'record'
                ex = sorted(sig['examples'], key=lambda x: -x[0])
                names = [bills_out[i]['label'] + ' (' + (bills_out[i]['title'] or '')[:60] + ')' for _, i, _ in ex[:2]]
                if score is None:
                    summary = f"No public statements found. The only related bills on record are neutral ones (research, education or government use), such as {'; '.join(names)}."
                else:
                    summary = f"No public statements found. Record only: sponsored or cosponsored {sig['n']} related bill{'s' if sig['n']!=1 else ''}, including {'; '.join(names)}."
                for w, i, role in ex[:6]:
                    bo = bills_out[i]
                    if norm_url(bo['url']) in seen_urls: continue
                    evidence.append({'type': role, 'date': None, 'title': f"{'Sponsored' if role=='sponsor' else 'Cosponsored'} {bo['label']}: {bo['title']}", 'url': bo['url'], 'quote': None, 'what_it_shows': bo['what'], 'verified': 'record'})
                    seen_urls.add(norm_url(bo['url']))
            if not summary:
                summary = 'No public position found.'
            positions[key] = {'score': score, 'label': d['scale'][score] if score is not None else 'No public position found',
                              'confidence': conf if score is not None else 'none',
                              'basis': basis if score is not None else ('research' if rp else 'none'),
                              'summary': summary, 'evidence': evidence}
        for u in verdicts:
            if u not in used_verdicts and not (r and r.get('quote') and norm_url(r['quote']['url']) == u):
                warn(f"{m['bioguide']}: verification check for {u[:80]} matched no evidence URL")
        # notable quote: keep only if not refuted
        quote = dict((r or {}).get('quote') or {}) or None
        if quote:
            vd = verdicts.get(norm_url(quote['url']))
            if vd and vd['verdict'] in ('unsupported','wrong_person'):
                quote = None
            elif vd:
                if vd.get('corrected_quote'): quote['text'] = clean(vd['corrected_quote'])[:400]
                if vd.get('corrected_date'): quote['date'] = vd['corrected_date']
                quote['verified'] = vd['verdict']
            else:
                quote['verified'] = 'unchecked'
        # groups and PACs
        groups = list((r or {}).get('groups', []))
        for g in ls_groups.get(m['bioguide'], []):
            if not any(g.lower()[:30] in x.lower() or x.lower()[:30] in g.lower() for x in groups):
                groups.append(clean(g))
        pacs = []
        for p_ in ls_pacs.get(m['bioguide'], []):
            pacs.append({'pac': clean(p_.get('pac')), 'agenda': clean(p_.get('agenda')), 'kind': p_.get('kind') if p_.get('kind') in ('supported','opposed') else 'supported', 'detail': clean(p_.get('detail')), 'url': safe_url(p_.get('url'))})
        # activity
        n119 = sum(1 for it in mbills if it['id'].startswith('119'))
        nspon = sum(1 for it in mbills if it['role']=='sponsor' and it['id'].startswith('119'))
        n_ai = sum(1 for it in mbills if bills_out[it['id']]['lane'] in ('ai_risk_control','data_centers_energy','preemption_state_laws','deepfakes_likeness_copyright','ai_government_research','workers_jobs','chips_china_export'))
        leader_role = any(re.search(r'\b(chair(man|woman|person)?|ranking member|co-chair|vice-chair|lead sponsor|author|negotiators?)\b', g, re.I) for g in groups)
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
            'url': safe_url(m['url']), 'wikipedia': m['wikipedia'], 'photo': photo, 'first_term': m['first_term_start'][:4],
            'committees': [c['name'] for c in m['committees']],
            'groups': groups, 'pacs': pacs,
            'activity': {'level': level, 'n_bills_119': n119, 'n_sponsored_119': nspon, 'n_ai_bills': n_ai, 'n_statements': n_statements},
            'positions': positions, 'votes': mv, 'bills': mbills,
            'signature': (r or {}).get('signature'),
            'quote': quote,
            'researched': bool(r),
        })

    # ---- stats
    stats = {'members': len(out_members), 'senate': sum(1 for x in out_members if x['chamber']=='Senate'), 'house': sum(1 for x in out_members if x['chamber']=='House'),
             'researched': sum(1 for x in out_members if x['researched']), 'verified_members': len(verification), 'dropped_evidence': n_dropped_evidence}
    for d in DIMENSIONS:
        stats[d['key']] = dict(collections.Counter(str(x['positions'][d['key']]['score']) for x in out_members))
    stats['activity'] = dict(collections.Counter(x['activity']['level'] for x in out_members))
    stats['basis'] = dict(collections.Counter(p['basis'] for x in out_members for p in x['positions'].values()))
    stats['pac_members'] = sum(1 for x in out_members if x['pacs'])

    os.makedirs(SITE, exist_ok=True)
    os.makedirs(os.path.join(SITE, 'photos'), exist_ok=True)
    for p in glob.glob(os.path.join(SRC, 'photos', '*.jpg')):
        dst = os.path.join(SITE, 'photos', os.path.basename(p))
        if not os.path.exists(dst) or os.path.getmtime(p) > os.path.getmtime(dst):
            shutil.copy2(p, dst)
    explainers = landscape.get('explainers', {})
    for ex in explainers.values():
        for b in ex.get('bills', []):
            b['url'] = safe_url(b.get('url'))
            for k in ('title','what','status','label'): b[k] = clean(b.get(k))
    data = {
        'generated': datetime.date.today().isoformat(), 'congress': 119,
        'dimensions': [{k: v for k, v in d.items() if k != 'lanes'} | {'scale': {str(k): v for k, v in d['scale'].items()}} for d in DIMENSIONS],
        'votes': votes_out, 'bills': bills_out, 'members': out_members, 'stats': stats,
        'landscape': {'explainers': explainers},
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(SITE, 'data.json'), 'w') as f:
        f.write(payload)
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
    with open(os.path.join(ROOT, 'build-warnings.log'), 'w') as f:
        f.write('\n'.join(WARN) + ('\n' if WARN else ''))
    print('build stamp', stamp)
    print(f"wrote docs/data.json: {len(out_members)} members, {len(bills_out)} bills, {len(votes_out)} key votes, {stats['researched']} researched, {len(verification)} verified, {len(WARN)} warnings (build-warnings.log)")
    print('stats', json.dumps(stats))

if __name__ == '__main__':
    main()
