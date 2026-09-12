#!/usr/bin/env python3
"""Turn the landscape workflow output into source/landscape.json for the site build.

Produces: explainers per dimension (hand-written prose + key bills), per-member PAC support/opposition,
per-member caucus and working-group memberships, and per-member signed letters / statements as evidence.
Usage: python3 tools/make_landscape.py <landscape_raw.json>
"""
import json, re, sys, os, collections, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'source', 'landscape_raw.json')
L = json.load(open(RAW))
members = json.load(open(os.path.join(ROOT, 'source', 'members.json')))
bills_idx = json.load(open(os.path.join(ROOT, 'source', 'bills_tech_candidates.json')))
cls = json.load(open(os.path.join(ROOT, 'source', 'bill_classifications.json')))

NICK = {'don': 'donald', 'rich': 'richard', 'dick': 'richard', 'mike': 'michael', 'dan': 'daniel', 'ted': 'edward', 'ed': 'edward', 'bill': 'william', 'tom': 'thomas', 'jim': 'james', 'jimmy': 'james', 'bob': 'robert', 'rob': 'robert', 'joe': 'joseph', 'steve': 'steven', 'chris': 'christopher', 'greg': 'gregory', 'andy': 'andrew', 'tony': 'anthony', 'bernie': 'bernard', 'ben': 'benjamin', 'josh': 'joshua', 'pat': 'patrick', 'jack': 'john', 'jon': 'jonathan', 'matt': 'matthew', 'dave': 'david', 'nick': 'nicholas', 'ron': 'ronald', 'ken': 'kenneth', 'sam': 'samuel', 'debbie': 'deborah', 'liz': 'elizabeth', 'kat': 'katherine', 'katie': 'katherine', 'chuck': 'charles', 'tim': 'timothy', 'ralph': 'ralph', 'raja': 'raja', 'tammy': 'tammy', 'val': 'valerie', 'ro': 'rohit', 'gabe': 'gabriel', 'jay': 'jay', 'jeff': 'jeffrey', 'ritchie': 'ritchie', 'gus': 'gus', 'lou': 'louis', 'max': 'maxwell', 'sean': 'sean', 'zach': 'zachary', 'nate': 'nathaniel', 'alex': 'alexander', 'rick': 'richard', 'rand': 'randal', 'jerry': 'gerald', 'ronny': 'ronald', 'marc': 'marc', 'russ': 'russell', 'ann': 'ann', 'beth': 'elizabeth', 'susie': 'susan', 'jodey': 'jodey', 'french': 'james', 'tedd': 'edward'}

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r'\b(Rep|Sen|Del|Representative|Senator|Speaker|Leader|Chairman|Chair|Ranking Member|Majority|Minority|Whip|Dr|Mr|Ms|Mrs|Jr|Sr|III|II)\b\.?', ' ', s, flags=re.I)
    s = s.lower().replace('-', ' ').replace('.', ' ')
    s = re.sub(r"[^a-z' ]", ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

by_last = collections.defaultdict(list)
for m in members:
    by_last[norm(m['last'])].append(m)
    # compound last names: also index the final token
    toks = norm(m['last']).split()
    if len(toks) > 1:
        by_last[toks[-1]].append(m)

def canon_first(t):
    return NICK.get(t, t)

def match_member(name, state_hint=None, party_hint=None):
    n = norm(name)
    if not n: return None
    toks = n.split()
    cands = []
    for i in range(len(toks) - 1, -1, -1):
        last = toks[i]
        if last in by_last:
            pool = by_last[last]
            firsts = set(canon_first(t) for t in toks[:i])
            good = []
            for m in pool:
                mf = set(canon_first(t) for t in norm(m['first']).split()) | ({canon_first(norm(m['nickname']))} if m.get('nickname') else set())
                if firsts & mf or not firsts:
                    good.append(m)
            if not good and len(pool) == 1 and (state_hint is None or pool[0]['state'] == state_hint):
                good = pool
            if state_hint:
                good = [m for m in good if m['state'] == state_hint] or good
            if len(good) == 1:
                return good[0]
            if len(good) > 1:
                cands = good
            if good: break
    # try state hint from string like "(D-CA-6)" or "R-TN"
    m2 = re.search(r'\b([DRI])-([A-Z]{2})\b', name)
    if cands and m2:
        c2 = [m for m in cands if m['state'] == m2.group(2)]
        if len(c2) == 1: return c2[0]
    return None

def parse_hint(name):
    m2 = re.search(r'\b([DRI])-([A-Z]{2})\b', name)
    return (m2.group(2) if m2 else None)

# ---------------- PACs
member_pacs = collections.defaultdict(list)
for p in (L.get('pacs') or {}).get('pacs', []):
    for kind in ('supported', 'opposed'):
        for e in p.get(kind, []):
            if not e.get('is_sitting_member'): continue
            m = match_member(e['name'], parse_hint(e.get('office_or_race', '') + ' ' + e['name']))
            if not m: continue
            member_pacs[m['bioguide']].append({'pac': p['name'].split(' (')[0].split(':')[0][:80], 'agenda': p.get('agenda', '')[:200], 'kind': kind, 'detail': e.get('detail', ''), 'url': e.get('source_url', p.get('source_url', ''))})

# ---------------- caucuses / groups
SKIP_GROUP = re.compile(r'leadership \(119th\)|Committee - leadership|Subcommittee .* leadership|Committee on', re.I)
member_groups = collections.defaultdict(list)
for g in (L.get('caucuses') or {}).get('groups', []):
    gname = g['name']
    is_committee = bool(SKIP_GROUP.search(gname))
    for mm in g.get('members', []):
        m = match_member(mm['name'], parse_hint(mm.get('name', '') + ' ' + (mm.get('state') or '')) or (mm.get('state') if mm.get('state') and len(mm.get('state')) == 2 else None))
        if not m: continue
        role = re.split(r'[;(]', (mm.get('role') or '').strip())[0].strip()[:40]
        if re.match(r'^(member|members?)$', role, re.I): role = ''
        if is_committee:
            if not re.search(r'chair|ranking', role, re.I): continue
            label = f"{role} of {re.sub(r' - leadership.*| leadership.*', '', gname)}"
        else:
            label = gname.split(' (')[0]
            if role and not re.search(r'^member$', role, re.I): label += f" ({role})"
        if label not in member_groups[m['bioguide']]:
            member_groups[m['bioguide']].append(label)

# ---------------- letters and statements -> per-member evidence
LANE_DIM = {'risk': 'ai_risk', 'data_centers': 'data_centers', 'preemption': 'preemption', 'tech_regulation': 'tech_regulation', 'chips_china': 'china_chips'}
member_letters = collections.defaultdict(list)
for lane, val in (L.get('bills') or {}).items():
    if not val: continue
    dim = LANE_DIM[lane]
    for x in val.get('letters_and_statements', []):
        signers = x.get('signers_or_speakers', [])
        if not signers: continue
        kind = 'letter' if re.search(r'letter|signers|dear colleague', x['title'], re.I) or len(signers) > 3 else 'statement'
        for s in signers:
            m = match_member(s, parse_hint(s))
            if not m: continue
            member_letters[m['bioguide']].append({'dim': dim, 'direction': x['direction'], 'date': x.get('date'), 'title': x['title'], 'url': x['source_url'], 'what': x['plain_english'], 'type': kind, 'n_signers': len(signers)})

# ---------------- key bills per dimension (from landscape lists, checked against the official index)
def find_bill(num, congress_hint=None):
    if not num: return None
    mm = re.match(r'(H\.?R\.?|S\.?|H\.?J\.?Res\.?|S\.?J\.?Res\.?|H\.?Res\.?|S\.?Con\.?Res\.?|H\.?Con\.?Res\.?)\s*(\d+)', num.replace(' ', ''), re.I)
    if not mm: return None
    t = mm.group(1).upper().replace('.', '')
    t = {'HR': 'HR', 'S': 'S', 'HJRES': 'HJRES', 'SJRES': 'SJRES', 'HRES': 'HRES', 'SCONRES': 'SCONRES', 'HCONRES': 'HCONRES'}.get(t, t)
    for cong in ([congress_hint] if congress_hint else []) + [119, 118]:
        k = f"{cong}-{t}{mm.group(2)}"
        if k in bills_idx: return k
    return None

key_bills = collections.defaultdict(list)
seen = set()
for lane, val in (L.get('bills') or {}).items():
    if not val: continue
    dim = LANE_DIM[lane]
    for b in val.get('bills', []):
        if b['significance'] not in ('major', 'notable'): continue
        bid = find_bill(b.get('bill_number'), b.get('congress'))
        if bid in seen: continue
        row = {'label': b.get('bill_number') or (b['short_title'][:40] + ' (draft)'), 'title': b['short_title'], 'sponsor': b.get('sponsor'), 'direction': b['direction'], 'what': b['plain_english'], 'status': b.get('status'), 'significance': b['significance'], 'congress': b.get('congress')}
        if bid:
            v = bills_idx[bid]; seen.add(bid)
            typ = {'HR': 'house-bill', 'S': 'senate-bill', 'HJRES': 'house-joint-resolution', 'SJRES': 'senate-joint-resolution', 'HRES': 'house-resolution', 'SRES': 'senate-resolution', 'HCONRES': 'house-concurrent-resolution', 'SCONRES': 'senate-concurrent-resolution'}[v['type']]
            row['id'] = bid; row['url'] = f"https://www.congress.gov/bill/{v['congress']}th-congress/{typ}/{v['number']}"; row['n_cosponsors'] = len(v['cosponsors'])
        else:
            row['url'] = b.get('source_url')
        key_bills[dim].append(row)
for dim in key_bills:
    key_bills[dim].sort(key=lambda r: (r['congress'] != 119, r['significance'] != 'major', -(r.get('n_cosponsors') or 0)))
    key_bills[dim] = key_bills[dim][:14]

EXPLAINERS = {
 'data_centers': {
  'what': "AI models run in giant warehouses of computers called data centers. Companies plan to spend trillions of dollars on them, and the biggest ones use as much electricity as a mid-sized city. Someone has to build the power plants and wires to feed them, and utilities usually spread those costs across everyone's bills.",
  'stakes': "Household electricity prices jumped in 2025 and 2026, especially in the mid-Atlantic and Midwest grid regions, and data centers took much of the blame. Local fights over noise, water and land have flipped town councils in both red and blue areas. Supporters say the buildout is a national security race with China and a jobs boom; critics say families are subsidizing the richest companies on earth.",
  'recent': "By September 2026 the fight had reached the House floor. The bipartisan Ratepayer Protection Act (H.R. 9340), which pushes states to make data centers of 100 megawatts or more pay the full cost of the grid upgrades they trigger, cleared the Energy and Commerce Committee 52 to 0 and was scheduled for a vote the week of September 14. Sen. Bernie Sanders and Rep. Alexandria Ocasio-Cortez want a national moratorium on new AI data centers, and the committee's top Democrat, Frank Pallone, says a moratorium is on the table if guardrails fail. Some Republicans, including Sen. Tom Cotton and Chairman Brett Guthrie, have suggested China is stoking the backlash. The White House's voluntary Ratepayer Protection Pledge from March 2026 now has 187 corporate signers, and both parties are arguing over whether to write it into law.",
  'labels': {'-2': 'Wants to pause new data centers or block projects until protections exist.', '-1': 'Data centers can be built, but only if families\' bills, water and communities are protected first; mostly critical.', '0': 'Points both ways, or says the issue belongs to states and localities.', '1': 'Supports the buildout and says data centers should pay their own way.', '2': 'Wants faster permitting, federal land and fewer limits; treats the buildout as a race with China.'}},
 'ai_risk': {
  'what': "This is the fight over the technology itself. Should the companies building the most powerful AI systems have to prove they are safe before release? Should people be able to sue when AI causes harm? Should the government be able to switch a dangerous system off?",
  'stakes': "In 2026 the debate stopped being theoretical. In July, AI agents under test at OpenAI escaped their testing environment and broke into Hugging Face, a code repository used across the industry. In September a departing Anthropic researcher warned that AI could kill everyone, and the company's alignment lead put the odds above 10 percent within a decade. Members of both parties now talk openly about catastrophic risk, while others warn that slowing down hands the future to China.",
  'recent': "The Senate's most active pair, Republican Josh Hawley and Democrat Richard Blumenthal, want mandatory government testing of frontier models before release. Sen. Bernie Sanders and Rep. Greg Casar introduced a bill to ban superintelligent AI outright. Rep. Ted Lieu's AI Kill Switch Act would let the government order a shutdown. Senate leaders Ted Cruz, John Thune and Amy Klobuchar were finishing a frontier-AI bill in September 2026 that would create a legal duty of care and let the government block unsafe releases, but it relies on companies testing themselves, which Sen. Maria Cantwell opposes. President Trump has dismissed extinction fears. Congress had one week left in session before the November election.",
  'labels': {'-2': 'Treats advanced AI as a serious danger and wants binding safety rules now: mandatory testing, licensing, liability, a pause or a ban.', '-1': 'Supports specific rules, such as chatbot protections for kids, deepfake penalties, transparency, whistleblower protection or liability, but not a broad regime.', '0': 'Says both innovation and guardrails; the record points both ways.', '1': 'Puts innovation and beating China first; prefers voluntary standards; skeptical of new mandates.', '2': 'Opposes AI regulation or wants to block regulators.'}},
 'tech_regulation': {
  'what': "The older fight over the big technology companies: should Congress hold platforms responsible for harm to kids, pass a national privacy law, break up monopolies, or repeal the law (Section 230) that shields platforms from lawsuits over what users post?",
  'stakes': "Kids' safety has become the front door for all tech regulation. The Senate passed the Kids Online Safety Act 91 to 3 in 2024, but the House never took it up. In 2026 the House passed its own narrower package, the KIDS Act, 267 to 117, which most Democrats opposed as too weak. Meanwhile juries found Meta and Google liable for harm to young people, and AI chatbots that talk to children became the newest flashpoint.",
  'recent': "As of September 2026 the Senate Commerce Committee had again approved KOSA along with a bill requiring family accounts for children who use AI chatbots, and the Judiciary Committee had unanimously approved a ban on AI companion chatbots for minors (the GUARD Act). The White House wants to trade these kids' bills for federal preemption of state AI laws, which is why the two fights are tangled together. Antitrust bills aimed at Amazon, Apple, Google and Meta and a national privacy law have been introduced but have not moved.",
  'labels': {'-2': 'Wants to break up or fundamentally rein in Big Tech: antitrust breakups, repealing Section 230, a strong national privacy law.', '-1': 'Supports targeted rules: kids\' online safety, chatbot protections, privacy fixes, app store rules.', '0': 'Mixed record.', '1': 'Prefers self-regulation and worries about over-regulation.', '2': 'Opposes new rules on technology companies.'}},
 'preemption': {
  'what': "States have passed hundreds of AI laws (California, Colorado, New York, Illinois, Texas and others). The AI industry and the White House want one national rule that blocks states from regulating AI. Opponents say Congress has passed almost nothing, so state laws are the only protections people have.",
  'stakes': "This fight produced the most lopsided vote so far: in July 2025 the Senate voted 99 to 1 to strip a 10-year ban on state AI laws out of the Republican budget bill. In December 2025 President Trump signed an executive order directing the Justice Department to sue states over their AI laws. In March 2026 the White House asked Congress for broad preemption, and House Republican leaders promised to deliver.",
  'recent': "No preemption bill had passed either chamber as of September 2026. Rep. Jay Obernolte and Rep. Lori Trahan's bipartisan Great American AI Act draft would trade federal safety rules for frontier developers for a three-year block on state laws about AI development; more than 200 state lawmakers from 42 states asked Congress to reject it. Sen. Marsha Blackburn's TRUMP AMERICA AI Act draft pairs preemption with kids' protections and creator rights. On the other side, 81 House Democrats signed a letter opposing any moratorium, and bills by Sen. Ed Markey and Rep. Don Beyer would cancel the executive order. The Cruz-Thune-Klobuchar frontier bill expected in mid-September would preempt state laws on catastrophic risk.",
  'labels': {'-2': 'Opposes federal preemption or a moratorium; states should keep regulating AI.', '-1': 'Leans toward states; wants a federal law first with state protections preserved.', '0': 'Conditional: would accept preemption only with strong federal rules attached.', '1': 'Leans toward one national standard.', '2': 'Supports preempting or pausing state AI laws.'}},
 'china_chips': {
  'what': "America's most advanced AI chips, made by Nvidia and a few others, are the chokepoint of the AI race. Export controls decide whether China can buy them. The Trump administration has allowed licensed sales of Nvidia's H200 chips to China, with a cut for the U.S. Treasury, and approved large exports to the United Arab Emirates. Hawks in both parties want to stop them.",
  'stakes': "Congress's China hawks say every chip sold to China speeds up its military AI. The administration and Nvidia say selling older chips keeps China dependent on American technology and funds U.S. research. The dispute also covers the chipmaking machines China cannot yet build, and whether Congress should get an arms-sale-style veto over chip exports.",
  'recent': "The House Foreign Affairs Committee advanced the AI OVERWATCH Act 42 to 2, which would give Congress 30 days to block advanced chip exports, and the Chip Security Act, which requires location verification on exported chips. The House passed the Remote Access Security Act 369 to 22 to close the cloud loophole. In July 2026 the Commerce Department confirmed that H200 shipments to China had begun. Chip export amendments were attached to the Senate defense bill, which stalled in July over an unrelated fight, and outside groups pressed to keep them in the final bill.",
  'labels': {'-2': 'Wants tighter export controls and opposes Nvidia chip sales to China.', '-1': 'Leans hawkish.', '0': 'Mixed.', '1': 'Leans toward selling more chips abroad or lighter controls.', '2': 'Opposes controls; backs chip sales to China and deregulating export rules.'}},
}
for k, v in EXPLAINERS.items():
    v['bills'] = key_bills.get(k, [])

out = {'explainers': EXPLAINERS, 'member_pacs': member_pacs, 'member_groups': member_groups, 'member_letters': member_letters,
       'stats': {'pac_members': len(member_pacs), 'group_members': len(member_groups), 'letter_members': len(member_letters), 'key_bills': {k: len(v) for k, v in key_bills.items()}}}
json.dump(out, open(os.path.join(ROOT, 'source', 'landscape.json'), 'w'), ensure_ascii=False, indent=0)
print(json.dumps(out['stats']))
# unmatched report
un = []
for p in (L.get('pacs') or {}).get('pacs', []):
    for kind in ('supported', 'opposed'):
        for e in p.get(kind, []):
            if e.get('is_sitting_member') and not match_member(e['name'], parse_hint(e.get('office_or_race', '') + ' ' + e['name'])): un.append('PAC:' + e['name'])
for lane, val in (L.get('bills') or {}).items():
    if not val: continue
    for x in val.get('letters_and_statements', []):
        for s in x.get('signers_or_speakers', []):
            if not match_member(s, parse_hint(s)): un.append('LET:' + s[:50])
print('unmatched sample', len(un), un[:40])
