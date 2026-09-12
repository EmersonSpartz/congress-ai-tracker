import xml.etree.ElementTree as ET, json, os, re, glob, sys
OUT={}
for cong in ['118','119']:
    for d in glob.glob(f'src/BILLSTATUS-{cong}-*'):
        if d.endswith('.zip'): continue
        for f in glob.glob(d+'/*.xml'):
            try:
                b=ET.parse(f).getroot().find('bill')
            except Exception as e:
                print('ERR',f,e,file=sys.stderr); continue
            if b is None: continue
            typ=b.findtext('type'); num=b.findtext('number')
            bid=f"{cong}-{typ}{num}"
            titles=[t.findtext('title') for t in b.findall('titles/item')]
            short=[t.findtext('title') for t in b.findall('titles/item') if (t.findtext('titleType') or '').startswith('Short Title') ]
            summ=b.findtext('summaries/summary/text') or ''
            summ=re.sub('<[^>]+>',' ',summ); summ=re.sub(r'\s+',' ',summ).strip()
            OUT[bid]={
              'id':bid,'congress':int(cong),'type':typ,'number':int(num),
              'title':b.findtext('title'),
              'short_titles':sorted(set(short))[:6],
              'introduced':b.findtext('introducedDate'),
              'policy_area':b.findtext('policyArea/name'),
              'subjects':[s.findtext('name') for s in b.findall('subjects/legislativeSubjects/item')],
              'sponsor':[(s.findtext('bioguideId'),s.findtext('fullName')) for s in b.findall('sponsors/item')],
              'cosponsors':[(s.findtext('bioguideId'),s.findtext('sponsorshipDate'),s.findtext('isOriginalCosponsor'),s.findtext('sponsorshipWithdrawnDate')) for s in b.findall('cosponsors/item')],
              'latest_action':b.findtext('latestAction/text'),
              'latest_action_date':b.findtext('latestAction/actionDate'),
              'laws':[(l.findtext('type'),l.findtext('number')) for l in b.findall('laws/item')],
              'committees':[c.findtext('name') for c in b.findall('committees/item')],
              'summary':summ[:1200],
              'n_actions':len(b.findall('actions/item')),
              'related':[(r.findtext('type'),r.findtext('number'),r.findtext('congress')) for r in b.findall('relatedBills/item')][:20],
            }
json.dump(OUT,open('data/bills_index.json','w'))
print(len(OUT))
# keyword filter
KW=re.compile(r"\b(artificial intelligence|\bA\.?I\.?\b|machine learning|algorithm|deepfake|deep fake|synthetic media|digital replica|chatbot|chat bot|large language|foundation model|frontier model|generative|automated decision|data center|datacenter|data centre|semiconductor|chips? (act|security|export)|export control|Nvidia|CHIPS|Section 230|social media|online safety|children.{0,20}online|COPPA|kids online|app store|privacy|antitrust|Big Tech|platform|TikTok|foreign adversary|autonomous|robocall|voice clon|likeness|NO FAKES|take it down|surveillance|facial recognition|biometric|quantum|compute|GPU|ratepayer|large load|electric(ity)? (rate|bill|price)|PJM|grid reliability|neural|AI safety|AI model)", re.I)
hits={k:v for k,v in OUT.items() if KW.search((v['title'] or '')+' '+' '.join(v['short_titles'])+' '+(v['policy_area'] or '')+' '+' '.join(v['subjects'])+' '+v['summary'])}
json.dump(hits,open('data/bills_tech_candidates.json','w'))
print('candidates',len(hits))
ai=re.compile(r"\b(artificial intelligence|\bA\.?I\.?\b|machine learning|deepfake|chatbot|frontier model|foundation model|generative|data center|datacenter|algorithm)",re.I)
aih={k:v for k,v in OUT.items() if ai.search((v['title'] or '')+' '+' '.join(v['short_titles'])+' '+' '.join(v['subjects'])+' '+v['summary'])}
print('ai-ish',len(aih), 'ai-ish 119', sum(1 for v in aih.values() if v['congress']==119))
json.dump(aih,open('data/bills_ai_candidates.json','w'))
