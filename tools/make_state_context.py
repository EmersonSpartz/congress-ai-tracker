"""Build per-state context markdown files for the member-research agents from the landscape workflow output."""
import json, os, collections, sys
SP=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L=json.load(open(f'{SP}/data/landscape_raw.json'))
members=json.load(open(f'{SP}/data/members.json'))
NAMES={'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming','DC':'District of Columbia','PR':'Puerto Rico','GU':'Guam','VI':'U.S. Virgin Islands','AS':'American Samoa','MP':'Northern Mariana Islands'}
CODE={v.lower():k for k,v in NAMES.items()}
# collect region state entries
state_entries={}
for reg,val in (L.get('data_center_regions') or {}).items():
    if not val: continue
    for st in val.get('states',[]):
        name=st['state'].strip()
        code=CODE.get(name.lower()) or (name.upper() if len(name)==2 else None)
        if not code:
            for k,v in NAMES.items():
                if v.lower() in name.lower(): code=k; break
        if not code: print('unmatched state',name,file=sys.stderr); continue
        state_entries[code]=st
# member last names by state for matching events
bystate=collections.defaultdict(list)
for m in members: bystate[m['state']].append(m)
def mentions(text, m):
    t=text.lower()
    return m['last'].lower() in t and (m['first'].lower() in t or m['chamber'][:3].lower() in t or True)
events=[]
for k in ['summer_2026','spring_2026']:
    ev=(L.get('recent') or {}).get(k) or {}
    events+=ev.get('events',[])
pac_hits=collections.defaultdict(list)
for p in (L.get('pacs') or {}).get('pacs',[]):
    for kind in ['supported','opposed']:
        for e in p.get(kind,[]):
            pac_hits[e['name'].lower()].append((p['name'],kind,e.get('detail',''),e.get('source_url','')))
group_hits=collections.defaultdict(list)
for g in (L.get('caucuses') or {}).get('groups',[]):
    for mm in g.get('members',[]):
        group_hits[mm['name'].lower()].append((g['name'],mm.get('role','')))
eng={e['name'].lower():e for e in (L.get('engaged') or {}).get('members',[])}
letters=[]
for lane,val in (L.get('bills') or {}).items():
    if val: letters+= [dict(x,lane=lane) for x in val.get('letters_and_statements',[])]
os.makedirs(f'{SP}/data/state_context',exist_ok=True)
for code,ms in bystate.items():
    out=[f"# {NAMES.get(code,code)} ({code}): context for researching its members of Congress\n"]
    st=state_entries.get(code)
    if st:
        out.append(f"## AI data center politics in {NAMES.get(code,code)} (heat: {st.get('heat')})\n{st.get('summary','')}\n")
        if st.get('fights'):
            out.append("### Specific fights")
            for f in st['fights']:
                out.append(f"- {f.get('place','')}: {f.get('project','')} | {f.get('issue','')} | {f.get('status','')} | {f.get('source_url','')}")
        if st.get('members_on_record'):
            out.append("\n### Members already found on record about data centers (verify and expand; the quotes below came from a first-pass researcher and must be re-checked at the URL)")
            for r in st['members_on_record']:
                out.append(f"- {r.get('name')} ({r.get('party','')}, {r.get('chamber','')}): {r.get('position','')} | quote: {r.get('quote') or ''} | {r.get('date') or ''} | {r.get('source_url','')}")
    else:
        out.append("## AI data center politics: no state-specific brief was produced; search local press for data center fights, electricity prices, and members' statements.\n")
    out.append("\n## Per-member leads from the landscape research (recent events, PAC money, caucuses, engagement sketches)")
    for m in ms:
        leads=[]
        key=m['name'].lower(); last=m['last'].lower()
        for e in events:
            for mi in e.get('members_involved',[]):
                n=mi.get('name','').lower()
                if last in n and (m['first'].lower().split()[0] in n or len(n)<40):
                    leads.append(f"EVENT {e.get('date')}: {e.get('headline')} :: {mi.get('what_they_did_or_said')} | {mi.get('source_url') or e.get('source_url')}")
        for n,hits in pac_hits.items():
            if last in n and m['first'].lower().split()[0] in n:
                for h in hits: leads.append(f"PAC {h[0]} {h[1]}: {h[2]} | {h[3]}")
        for n,hits in group_hits.items():
            if last in n and (m['first'].lower().split()[0] in n or len(n.split())<=2):
                for h in hits: leads.append(f"GROUP: {h[0]} ({h[1]})")
        for n,e in eng.items():
            if last in n and m['first'].lower().split()[0] in n:
                leads.append(f"SKETCH: {e.get('stance_sketch')} | lanes: {', '.join(e.get('lanes',[]))} | {e.get('source_url')}")
        for l in letters:
            for s in l.get('signers_or_speakers',[]):
                sl=s.lower()
                if last in sl and (m['first'].lower().split()[0] in sl or m['state'].lower() in sl or len(sl.split())<=3):
                    leads.append(f"LETTER/STATEMENT ({l.get('lane')}, {l.get('direction')}): {l.get('title')} :: {l.get('plain_english')} | {l.get('source_url')}")
        out.append(f"\n### {m['name']} ({m['party'][0]}, {m['chamber']}{'' if m['chamber']=='Senate' else ' district '+str(m['district'])})")
        out += ['- '+x for x in dict.fromkeys(leads)] or ['- No leads from the landscape pass. Search from scratch.']
    open(f'{SP}/data/state_context/{code}.md','w').write('\n'.join(out))
print('wrote', len(bystate), 'state context files; states with data-center briefs:', len(state_entries))
