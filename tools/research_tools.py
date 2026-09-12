#!/usr/bin/env python3
"""research_tools.py: search and fetch helpers for research agents (WebSearch budget is exhausted in this session).

Usage:
  research_tools.py news "<query>" [--n 12] [--decode 5]      Google News RSS search; decodes the first --decode article links to real URLs (about 5-30 s per call)
  research_tools.py site <domain-or-url> [--match REGEX] [--from 2025] [--limit 80]
                                                              List archived URLs on a site (Wayback CDX), filtered by a regex on the URL (default: AI/tech words)
  research_tools.py fetch <url> [--max 15000] [--grep "phrase"] Fetch a page as plain text with a browser UA; falls back to the Wayback Machine when blocked.
                                                              --grep prints 350-char windows around each match instead of the whole text (for verbatim quotes)
  research_tools.py decode <news.google.com/rss/articles/... url>
Output: one JSON object per line (news/site/web/decode). fetch prints a JSON header line, then the text.
"""
import sys, os, re, json, time, hashlib, random, html, urllib.request, urllib.parse, urllib.error, subprocess, gzip, zlib, warnings, fcntl
warnings.filterwarnings('ignore')

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cache')
os.makedirs(CACHE, exist_ok=True)
AI_RE = r'artificial|intelligen|\bai\b|[-_/]ai[-_/]|\bai[-_]|data[-_]?cent|chatbot|deepfake|deep[-_]fake|nvidia|chip|semiconductor|big[-_]tech|section[-_]230|social[-_]media|online[-_]safety|kids?[-_]online|algorithm|tech|privacy|antitrust|tiktok|robot|autonom|export[-_]control|grid|ratepayer|electric|energy|power[-_]bill|utility|moratorium|preempt|state[-_]law|nuclear|kosa|coppa'

def _cache_get(key):
    p = os.path.join(CACHE, hashlib.sha1(key.encode()).hexdigest() + '.json')
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 6 * 3600:
        try:
            return json.load(open(p))
        except Exception:
            return None
    return None

def _cache_put(key, val):
    p = os.path.join(CACHE, hashlib.sha1(key.encode()).hexdigest() + '.json')
    try:
        json.dump(val, open(p, 'w'))
    except Exception:
        pass

def _throttle(host, min_gap):
    """Cross-process rate limit: at most one request per min_gap seconds per host, shared by all agents."""
    p = os.path.join(CACHE, 'rl_' + re.sub(r'[^a-z0-9]', '_', host) + '.lock')
    with open(p, 'a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0); last = float((f.read() or '0').strip() or 0)
            wait = last + min_gap - time.time()
            if wait > 0: time.sleep(wait)
            f.seek(0); f.truncate(); f.write(str(time.time())); f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

HOST_GAP = {'news.google.com': 0.6, 'web.archive.org': 0.7, 'archive.org': 0.7}

def _get(url, timeout=30, tries=3, accept=None):
    """Return (status, final_url, content_type, bytes). Raises on total failure."""
    last = None
    host = urllib.parse.urlparse(url).netloc.lower()
    for h, gap in HOST_GAP.items():
        if host.endswith(h): _throttle(h, gap); break
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept or 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'identity'})
            r = urllib.request.urlopen(req, timeout=timeout)
            data = r.read()
            if data[:2] == b'\x1f\x8b':
                try: data = gzip.decompress(data)
                except Exception: pass
            elif (r.headers.get('Content-Encoding') or '').lower() == 'deflate':
                try: data = zlib.decompress(data, -zlib.MAX_WBITS)
                except Exception: pass
            return r.status, r.geturl(), r.headers.get('Content-Type', ''), data
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 404, 410, 451):
                return e.code, url, '', b''
            time.sleep((15 if e.code == 429 else 4) * (a + 1) + random.random() * 3)
        except Exception as e:
            last = e
            time.sleep(3 * (a + 1))
    raise RuntimeError(f'fetch failed: {last}')

def html_to_text(raw):
    t = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw
    title = re.search(r'<title[^>]*>(.*?)</title>', t, re.S | re.I)
    title = html.unescape(re.sub(r'\s+', ' ', title.group(1))).strip() if title else ''
    pub = None
    for pat in [r'property="article:published_time"\s+content="([^"]+)"', r'content="([^"]+)"\s+property="article:published_time"', r'"datePublished"\s*:\s*"([^"]+)"', r'name="pubdate"\s+content="([^"]+)"', r'name="date"\s+content="([^"]+)"', r'<time[^>]*datetime="([^"]+)"']:
        m = re.search(pat, t, re.I)
        if m:
            pub = m.group(1)[:10]; break
    t = re.sub(r'<(script|style|noscript|svg|head)[^>]*>.*?</\1>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'<!--.*?-->', ' ', t, flags=re.S)
    t = re.sub(r'<(br|/p|/div|/li|/h[1-6]|/tr|/blockquote|/section|/article)[^>]*>', '\n', t, flags=re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = html.unescape(t)
    t = re.sub(r'[ \t\r\f\v]+', ' ', t)
    t = re.sub(r'\n\s*\n+', '\n', t)
    return title, pub, t.strip()

def pdf_to_text(data):
    try:
        p = subprocess.run(['pdftotext', '-layout', '-', '-'], input=data, capture_output=True, timeout=60)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.decode('utf-8', 'replace')
    except Exception:
        pass
    try:
        import PyPDF2  # optional
        from io import BytesIO
        r = PyPDF2.PdfReader(BytesIO(data))
        return '\n'.join((pg.extract_text() or '') for pg in r.pages[:40])
    except Exception:
        return ''

def wayback_snapshot(url):
    try:
        st, _, _, b = _get('http://archive.org/wayback/available?url=' + urllib.parse.quote(url, safe=''), timeout=30)
        d = json.loads(b.decode() or '{}')
        snap = (d.get('archived_snapshots') or {}).get('closest')
        if snap and snap.get('available'):
            return snap['timestamp'], snap['url']
    except Exception:
        pass
    return None, None

def cmd_fetch(url, maxc=15000, grep=None):
    time.sleep(0.3 + random.random() * 0.7)
    via = 'direct'; status = None; final = url; ctype = ''; data = b''
    try:
        status, final, ctype, data = _get(url)
    except Exception as e:
        status = f'error: {e}'
    blocked = (not isinstance(status, int)) or status >= 400 or (len(data) < 800 and b'Access Denied' in data) or b'Access Denied</TITLE>' in data[:600]
    if blocked:
        wb = 'https://web.archive.org/web/2026id_/' + url
        try:
            st2, final2, ctype2, data2 = _get(wb, timeout=60)
            if isinstance(st2, int) and st2 == 200 and len(data2) > 500:
                status, final, ctype, data = st2, final2, ctype2, data2
                m = re.search(r'/web/(\d{14})', final2 or '')
                via = 'wayback:' + (m.group(1)[:8] if m else 'latest')
            else:
                status = f'{status}; wayback {st2}'
        except Exception as e:
            status = f'{status}; wayback error: {e}'
    if 'pdf' in (ctype or '').lower() or url.lower().endswith('.pdf'):
        text = pdf_to_text(data); title = os.path.basename(url); pub = None
    else:
        title, pub, text = html_to_text(data)
    hdr = {'url': url, 'final_url': final, 'status': status, 'via': via, 'title': title, 'published': pub, 'chars': len(text)}
    print(json.dumps(hdr, ensure_ascii=False))
    if grep:
        terms = [g for g in grep if g] if isinstance(grep, list) else [grep]
        low = text.lower(); shown = 0
        for term in terms:
            for m in re.finditer(re.escape(term.lower()), low):
                s = max(0, m.start() - 350); e = min(len(text), m.end() + 350)
                print(f'--- match "{term}" @{m.start()}:\n' + text[s:e].replace('\n', ' ') + '\n')
                shown += 1
                if shown >= 6: return
        if not shown:
            print('--- no match for', terms, '(page text length', len(text), '). First 1500 chars:\n' + text[:1500])
    else:
        print(text[:maxc])
        if len(text) > maxc:
            print(f'\n[... truncated {len(text) - maxc} more characters; use --grep to find passages]')

def cmd_news(query, n=12, decode=5, budget=60):
    t0 = time.time()
    key = 'news:' + query
    c = _cache_get(key)
    if c is None:
        time.sleep(0.8 + random.random() * 1.2)
        u = 'https://news.google.com/rss/search?q=' + urllib.parse.quote(query) + '&hl=en-US&gl=US&ceid=US:en'
        st, _, _, b = _get(u, accept='application/rss+xml,application/xml,text/xml,*/*')
        t = b.decode('utf-8', 'replace')
        items = []
        for it in re.findall(r'<item>(.*?)</item>', t, re.S):
            ti = re.search(r'<title>(.*?)</title>', it, re.S); li = re.search(r'<link>(.*?)</link>', it, re.S)
            pd = re.search(r'<pubDate>(.*?)</pubDate>', it); src = re.search(r'<source[^>]*>(.*?)</source>', it)
            items.append({'title': html.unescape(ti.group(1)).strip() if ti else '', 'gnews_url': li.group(1).strip() if li else '', 'date': pd.group(1)[5:16] if pd else '', 'source': html.unescape(src.group(1)) if src else ''})
        c = items
        _cache_put(key, c)
    out = c[:n]
    if decode:
        try:
            from googlenewsdecoder import gnewsdecoder
        except Exception:
            gnewsdecoder = None
        for it in out[:decode]:
            if it.get('url'): continue
            if time.time() - t0 > budget:
                it['url'] = None; it['note'] = 'not decoded (time budget); run: research_tools.py decode <gnews_url>'; continue
            if gnewsdecoder and it['gnews_url']:
                dk = 'decode:' + it['gnews_url']
                dc = _cache_get(dk)
                if dc is None:
                    try:
                        r = gnewsdecoder(it['gnews_url'], interval=1)
                        dc = r.get('decoded_url') if r.get('status') else None
                    except Exception:
                        dc = None
                    _cache_put(dk, dc or '')
                it['url'] = dc or None
        _cache_put(key, c)
    for it in out:
        print(json.dumps(it, ensure_ascii=False))
    if not out:
        print(json.dumps({'note': 'no results', 'query': query}))

def cmd_decode(u):
    from googlenewsdecoder import gnewsdecoder
    r = gnewsdecoder(u, interval=1)
    print(json.dumps({'decoded_url': r.get('decoded_url') if r.get('status') else None, 'message': r.get('message')}))

def cmd_site(domain, match=None, since='2025', limit=80):
    domain = re.sub(r'^https?://', '', domain).split('/')[0]
    key = f'site:{domain}:{since}'
    c = _cache_get(key)
    if c is None:
        time.sleep(0.5 + random.random())
        u = f'http://web.archive.org/cdx/search/cdx?url={domain}&matchType=domain&filter=statuscode:200&filter=mimetype:text/html&from={since}&output=json&fl=original,timestamp&collapse=urlkey&limit=8000'
        st, _, _, b = _get(u, timeout=90)
        try:
            d = json.loads(b.decode() or '[]')
        except Exception:
            d = []
        c = d[1:] if d else []
        _cache_put(key, c)
    rx = re.compile(match or AI_RE, re.I)
    seen = set(); rows = []
    for orig, ts in c:
        base = orig.split('?')[0].rstrip('/')
        if base in seen: continue
        slug = base.split('/', 3)[-1] if base.count('/') >= 3 else base
        if not rx.search(slug): continue
        if re.search(r'\.(jpg|png|gif|css|js|pdf|xml|ico|svg|woff2?)$', base, re.I): continue
        seen.add(base); rows.append({'url': base, 'archived': ts[:8]})
    rows.sort(key=lambda r: r['archived'], reverse=True)
    for r in rows[:limit]:
        print(json.dumps(r))
    print(json.dumps({'note': f'{len(rows)} matching archived URLs on {domain} since {since}; showing {min(limit, len(rows))}. Fetch any with: research_tools.py fetch <url>'}))

def cmd_web(query):
    print(json.dumps({'note': 'general web search engines block automated queries from this machine; use news and site instead'})); return
    time.sleep(1 + random.random())
    st, _, _, b = _get('https://www.mojeek.com/search?q=' + urllib.parse.quote(query))
    t = b.decode('utf-8', 'replace')
    n = 0
    for m in re.finditer(r'<a class="ob" href="([^"]+)"[^>]*>(.*?)</a>.*?(?:<p class="s">(.*?)</p>)?', t, re.S):
        u = html.unescape(m.group(1)); ti = html.unescape(re.sub('<[^>]+>', '', m.group(2))).strip(); sn = html.unescape(re.sub('<[^>]+>', '', m.group(3) or '')).strip()
        print(json.dumps({'title': ti, 'url': u, 'snippet': sn[:200]}, ensure_ascii=False)); n += 1
        if n >= 10: break
    if not n:
        print(json.dumps({'note': 'no results (or blocked)', 'status': st}))

def main(argv):
    if len(argv) < 2 or argv[1] in ('-h', '--help'):
        print(__doc__); return
    cmd = argv[1]; args = argv[2:]
    def opt(name, default=None, cast=str, multi=False):
        vals = []
        while name in args:
            i = args.index(name); vals.append(args[i + 1]); del args[i:i + 2]
        if multi: return [cast(v) for v in vals] if vals else default
        return cast(vals[-1]) if vals else default
    if cmd == 'news':
        n = opt('--n', 12, int); dec = opt('--decode', 5, int); cmd_news(' '.join(args), n, dec)
    elif cmd == 'site':
        match = opt('--match'); since = opt('--from', '2025'); limit = opt('--limit', 80, int); cmd_site(args[0], match, since, limit)
    elif cmd == 'fetch':
        maxc = opt('--max', 15000, int); grep = opt('--grep', None, str, multi=True); cmd_fetch(args[0], maxc, grep)
    elif cmd == 'web':
        cmd_web(' '.join(args))
    elif cmd == 'decode':
        cmd_decode(args[0])
    else:
        print(__doc__)

if __name__ == '__main__':
    main(sys.argv)
