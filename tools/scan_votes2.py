import urllib.request, concurrent.futures, os, time, threading
UA={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'}
lock=threading.Lock(); stats={'ok':0,'404':0,'err':0}
def get(url):
    for a in range(4):
        try:
            r=urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30)
            return r.read().decode('utf-8','replace')
        except urllib.error.HTTPError as e:
            if e.code==404: return None
            time.sleep(5*(a+1))
        except Exception as e:
            time.sleep(5*(a+1))
    return 'ERR'
def fetch(ch, year, n):
    cong=118 if year<=2024 else 119
    p=f'votes/{"house" if ch=="h" else "senate"}/{year}_{n:03d}.csv'
    if os.path.exists(p): return
    t=get(f'https://www.govtrack.us/congress/votes/{cong}-{year}/{ch}{n}/export/csv')
    time.sleep(0.4)
    with lock:
        if t is None: stats['404']+=1
        elif t=='ERR' or not t.startswith(('Senate Vote','House Vote')): stats['err']+=1
        else:
            open(p,'w').write(t); stats['ok']+=1
jobs=[('s',2025,n) for n in range(1,720)]+[('s',2026,n) for n in range(1,520)]+[('h',2026,n) for n in range(1,480)]
with concurrent.futures.ThreadPoolExecutor(3) as ex:
    list(ex.map(lambda j: fetch(*j), jobs))
print(stats)
