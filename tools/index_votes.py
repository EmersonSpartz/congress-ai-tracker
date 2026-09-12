import glob, re, json, csv, xml.etree.ElementTree as ET, collections
members=json.load(open('data/members.json'))
gt2bg={m['govtrack']:m['bioguide'] for m in members}
KW=re.compile(r"(artificial intelligence|\bAI\b|A\.I\.|data center|deepfake|chatbot|algorithm|kids online|children.{0,25}online|COPPA|Section 230|TikTok|foreign adversary controlled application|semiconductor|chips? (security|export)|export control|Nvidia|privacy|antitrust|social media|online safety|take it down|NO FAKES|autonomous|DeepSeek|Kids Off Social|App Store|ratepayer|large load|state.{0,20}(AI|artificial intelligence) (law|regulation)|moratorium)", re.I)
votes={}
for f in sorted(glob.glob('votes/house/*.xml')):
    r=ET.parse(f).getroot(); md=r.find('vote-metadata')
    g=lambda t:(md.findtext(t) or '').strip()
    year,roll=re.findall(r'(\d{4})_(\d{3})',f)[0]
    vid=f"h{year}-{int(roll)}"
    desc=' | '.join([g('legis-num'),g('vote-question'),g('vote-desc'),g('amendment-author')])
    tally=collections.Counter()
    rec={}
    for rv in r.iter('recorded-vote'):
        leg=rv.find('legislator'); v=rv.findtext('vote')
        rec[leg.get('name-id')]=v; tally[v]+=1
    votes[vid]={'id':vid,'chamber':'House','congress':118 if int(year)<=2024 else 119,'year':int(year),'roll':int(roll),'date':g('action-date'),'measure':g('legis-num'),'question':g('vote-question'),'desc':g('vote-desc'),'result':g('vote-result'),'tally':dict(tally),'n':len(rec),'ai_kw':bool(KW.search(desc)),'votes':rec,
        'url':f"https://clerk.house.gov/Votes/{year}{int(roll)}", 'govtrack':f"https://www.govtrack.us/congress/votes/{118 if int(year)<=2024 else 119}-{year}/h{int(roll)}"}
for f in sorted(glob.glob('votes/senate/*.csv'))+sorted(glob.glob('votes/house/*.csv')):
    t=open(f).read()
    i=t.find('\nperson,')
    if i<0: continue
    head,body=t[:i].replace('\n',' '),t[i+1:]
    m=re.match(r'(Senate|House) Vote #(\d+) (\S+) - (.*)',head)
    if not m: continue
    ch,roll,dt,desc=m.groups(); year=dt[:4]
    vid=("s" if ch=='Senate' else "h")+f"{year}-{int(roll)}"
    if vid in votes: continue
    rec={}; tally=collections.Counter(); unmatched=0
    for row in csv.DictReader(body.splitlines()):
        pid=int(row['person']); bg=gt2bg.get(pid)
        if bg: rec[bg]=row['vote']
        else: unmatched+=1
        tally[row['vote']]+=1
    cong=118 if int(year)<=2024 else 119
    votes[vid]={'id':vid,'chamber':ch,'congress':cong,'year':int(year),'roll':int(roll),'date':dt[:10],'measure':desc.split(':')[0],'question':'','desc':desc,'result':'','tally':dict(tally),'n':len(rec)+unmatched,'unmatched':unmatched,'ai_kw':bool(KW.search(desc)),'votes':rec,
        'url':None,'govtrack':f"https://www.govtrack.us/congress/votes/{cong}-{year}/{'s' if ch=='Senate' else 'h'}{int(roll)}"}
json.dump(votes,open('data/votes_index.json','w'))
print('votes',len(votes), collections.Counter((v['chamber'],v['year']) for v in votes.values()))
hits=[v for v in votes.values() if v['ai_kw']]
print('keyword hits',len(hits))
for v in sorted(hits,key=lambda v:(v['year'],v['chamber'],v['roll'])): print(v['id'],v['date'],(v['measure']+' '+v['question']+' '+v['desc'])[:150].replace('\n',' '))
