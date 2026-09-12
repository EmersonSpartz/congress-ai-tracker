/* Where Congress Stands on AI: front-end. Vanilla JS, hash routing, data.json. */
(function () {
  'use strict';
  const $ = (sel, el) => (el || document).querySelector(sel);
  const app = $('#app');
  // BUILD_STAMP is replaced by build.py with a content hash so browsers refetch data.json after each deploy.
  let D = null; // data
  let byId = {};
  const DIMS = () => D.dimensions;
  const PARTY_NAME = { D: 'Democrat', R: 'Republican', I: 'Independent' };
  const ACT_DESC = { Leader: 'Leads on AI: sponsors major AI bills or chairs a relevant group', Active: 'Active: several AI bills or public statements', Some: 'Some activity: at least one relevant bill or statement', Quiet: 'Quiet: no AI-related bills or statements found' };
  const ETYPE = { vote: 'Vote', sponsor: 'Sponsored bill', cosponsor: 'Cosponsored bill', letter: 'Letter', statement: 'Statement', hearing: 'Hearing', interview: 'Interview', op_ed: 'Op-ed', social_post: 'Post', pac: 'Campaign money', other: 'Source' };
  const VER = { confirmed: 'Source checked', partially_supported: 'Source partly supports', record: 'Official record', landscape: 'From signed letter or statement', unchecked: 'Not yet re-checked', unreachable: 'Source unreachable' };

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fmtDate = d => {
    if (!d) return '';
    const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(d);
    if (!m) return esc(d);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return (m[3] ? parseInt(m[3], 10) + ' ' : '') + months[parseInt(m[2], 10) - 1] + ' ' + m[1];
  };
  const seat = m => m.chamber === 'Senate' ? `${m.state_name} senator` : (m.district === 0 ? `${m.state_name}, at-large` : `${m.state_name} District ${m.district}`);
  const seatShort = m => m.chamber === 'Senate' ? `${m.state} Sen.` : (m.district === 0 ? `${m.state} at-large` : `${m.state}-${m.district}`);
  const title = m => m.chamber === 'Senate' ? 'Sen.' : (['DC', 'PR', 'GU', 'VI', 'AS', 'MP'].includes(m.state) ? 'Del.' : 'Rep.');
  const photo = (m, cls) => m.photo ? `<img class="${cls || ''}" src="${m.photo}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">` : `<div class="${cls || ''}" aria-hidden="true"></div>`;
  const partyChip = m => `<span class="party ${m.party}" title="${PARTY_NAME[m.party] || m.party}">${m.party}</span>`;
  const scaleLabel = (dim, s) => s == null ? 'No public position found' : dim.scale[String(s)];

  function chip(m, dim, opts) {
    opts = opts || {};
    const p = m.positions[dim.key];
    const s = p.score == null ? 'none' : String(p.score);
    const rec = p.basis === 'record' ? ' record' : '';
    const label = p.score == null ? (opts.short ? 'No position found' : 'No public position found') : p.label;
    const conf = p.score == null ? '' : `<span class="dot" aria-hidden="true"></span>`;
    const tip = p.score == null ? 'No public position found. Click for what we looked for.' : (rec ? 'Based on bill record only (no statements found). Click for the bills.' : 'Click for the summary and sources.');
    return `<span class="chip clickable${rec}${opts.lg ? ' lg' : ''}" data-s="${s}" data-m="${m.id}" data-d="${dim.key}" tabindex="0" role="button" title="${tip}" aria-label="${esc(dim.label)}: ${esc(label)}${rec ? ' (record only)' : ''}. Click for details">${conf}${esc(label)}${rec && opts.lg ? ' <span class="basis-tag">record only</span>' : ''}</span>`;
  }

  // ---------- popover
  const pop = $('#popover');
  function showPop(target, m, dimKey) {
    const dim = DIMS().find(d => d.key === dimKey);
    const p = m.positions[dimKey];
    const ev = (p.evidence || []).slice(0, 3);
    pop.innerHTML = `<button class="close" aria-label="Close">×</button>
      <h4>${esc(m.name)} <span class="muted">on</span> ${esc(dim.label)}</h4>
      <div>${chip(m, dim)} <span class="conf">${p.basis === 'record' ? 'from bill record only' : p.basis === 'letter' ? 'from a signed letter or statement' : p.confidence === 'none' ? '' : 'confidence: ' + esc(p.confidence)}</span></div>
      <p>${esc(p.summary)}</p>
      ${ev.length ? `<div class="src">${ev.map(e => `<div>• <a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>${e.date ? ` <span class="muted">(${fmtDate(e.date)})</span>` : ''}</div>`).join('')}</div>` : ''}
      <p class="small"><a href="#/member/${m.id}">Full profile and all sources</a></p>`;
    pop.hidden = false;
    const r = target.getBoundingClientRect();
    const pw = Math.min(380, window.innerWidth - 24);
    let left = window.scrollX + r.left;
    if (left + pw > window.scrollX + window.innerWidth - 12) left = window.scrollX + window.innerWidth - pw - 12;
    pop.style.left = left + 'px';
    pop.style.top = (window.scrollY + r.bottom + 8) + 'px';
    pop.style.width = pw + 'px';
    $('.close', pop).onclick = hidePop;
  }
  function hidePop() { pop.hidden = true; }
  document.addEventListener('click', e => {
    const c = e.target.closest('.chip.clickable[data-m]');
    if (c) { e.preventDefault(); showPop(c, byId[c.dataset.m], c.dataset.d); return; }
    if (!e.target.closest('#popover')) hidePop();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') hidePop();
    if (e.key === 'Enter' && e.target.classList && e.target.classList.contains('chip') && e.target.dataset.m) showPop(e.target, byId[e.target.dataset.m], e.target.dataset.d);
  });

  // ---------- routing
  function route() {
    hidePop();
    const h = location.hash.replace(/^#\/?/, '');
    const parts = h.split('/').filter(Boolean);
    const page = parts[0] || '';
    document.querySelectorAll('.nav a').forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#/' + page));
    document.title = ({ members: 'Every member: Where Congress Stands on AI', fights: 'The five fights: Where Congress Stands on AI', votes: 'Key votes: Where Congress Stands on AI', bills: 'The bills: Where Congress Stands on AI', about: 'How this works: Where Congress Stands on AI' })[page] || 'Where Congress Stands on AI';
    const top = () => window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    top();
    requestAnimationFrame(() => { if (!location.hash.includes('#', 2)) { top(); setTimeout(top, 30); } });
    if (page === 'member' && parts[1]) return renderMember(parts[1]);
    if (page === 'members') return renderMembers(parseQuery(parts.slice(1).join('/')));
    if (page === 'state' && parts[1]) return renderMembers({ state: parts[1].toUpperCase() });
    if (page === 'fights') return renderFights();
    if (page === 'votes') return renderVotes();
    if (page === 'bills') return renderBills();
    if (page === 'about') return renderAbout();
    return renderHome();
  }
  function parseQuery(q) {
    const o = {};
    if (!q) return o;
    q.replace(/^\?/, '').split('&').forEach(kv => { const [k, v] = kv.split('='); if (k) o[decodeURIComponent(k)] = decodeURIComponent(v || ''); });
    return o;
  }

  // ---------- home
  function renderHome() {
    const s = D.stats;
    const vote = D.votes.find(v => v.id === 's2025-363');
    const dc = D.members.filter(m => m.positions.data_centers.score != null).length;
    const riskKnown = D.members.filter(m => m.positions.ai_risk.score != null && m.positions.ai_risk.basis !== 'record').length;
    const leaders = s.activity.Leader || 0;
    const strict = D.members.filter(m => m.positions.ai_risk.score === -2).length;
    const preemptFor = D.members.filter(m => m.positions.preemption.score > 0).length;
    const preemptAgainst = D.members.filter(m => m.positions.preemption.score < 0).length;
    app.innerHTML = `
      <section class="hero">
        <h1>Where every member of Congress stands on AI</h1>
        <p class="lede">${D.members.length} senators and representatives. Five questions that will shape how artificial intelligence gets built and controlled. Every position links to a vote, a bill, or the member's own words. No guessing from party.</p>
        <p class="updated">Updated ${fmtDate(D.generated)}. 119th Congress.</p>
      </section>
      <section class="section" id="find">
        <div class="section-head"><h2>Find your representatives</h2><p>Pick your state, then your district if you know it.</p></div>
        <div class="finder">
          <div class="finder-row">
            <label>State <select id="f-state"><option value="">Choose a state</option>${states().map(st => `<option value="${st.code}">${esc(st.name)}</option>`).join('')}</select></label>
            <label>District <select id="f-dist" disabled><option value="">All</option></select></label>
            <span class="muted small">Not sure of your district? <a href="https://www.house.gov/representatives/find-your-representative" target="_blank" rel="noopener">Look it up by ZIP at house.gov</a>.</span>
          </div>
          <div id="f-out" class="cards"></div>
        </div>
      </section>
      <section class="section">
        <div class="tiles">
          <div class="tile"><div class="big">${vote ? tallyStr(vote) : '99 to 1'}</div><div class="cap">Senate vote in July 2025 to strip a 10-year ban on state AI laws out of the Republican budget bill. The one no: Sen. Thom Tillis.</div><a href="#/votes">See the vote</a></div>
          <div class="tile"><div class="big">${strict}</div><div class="cap">members who want strict rules on advanced AI now, treating it as a serious danger.</div><a href="#/members?ai_risk=-2">See who</a></div>
          <div class="tile"><div class="big">${dc}</div><div class="cap">members with a findable position on AI data centers, the fastest-growing fight in Congress.</div><a href="#/members?has=data_centers">See them</a></div>
          <div class="tile"><div class="big">${preemptAgainst} <span class="muted" style="font-size:1.2rem">vs</span> ${preemptFor}</div><div class="cap">members on record for letting states regulate AI, versus members who want one national rule that blocks state laws.</div><a href="#/fights">The fight explained</a></div>
          <div class="tile"><div class="big">${leaders}</div><div class="cap">members leading on AI: they sponsor the major bills or run the relevant committees and caucuses.</div><a href="#/members?activity=Leader">Meet them</a></div>
        </div>
      </section>
      <section class="section">
        <div class="section-head"><h2>The five fights, at a glance</h2><p>Each bar shows how members of each party line up. Teal means more guardrails, orange means more hands-off. Striped means we found no public position.</p></div>
        <div class="fights">${DIMS().map(fightCard).join('')}</div>
        <div class="legend" style="margin-top:12px">${legend()}</div>
      </section>
      <section class="section">
        <div class="section-head"><h2>Every member</h2><p>Search, filter, and sort. Click any position to see the source behind it.</p></div>
        <div id="table-host"></div>
      </section>`;
    bindFinder();
    mountTable($('#table-host'), {}, { compact: true });
  }
  function tallyStr(v) { const t = v.tally || {}; const y = (t.Yea || 0) + (t.Aye || 0) + (t.Yes || 0); const n = (t.Nay || 0) + (t.No || 0); return `${y} to ${n}`; }
  function states() {
    const seen = {};
    D.members.forEach(m => { seen[m.state] = m.state_name; });
    return Object.keys(seen).sort((a, b) => seen[a].localeCompare(seen[b])).map(c => ({ code: c, name: seen[c] }));
  }
  function bindFinder() {
    const st = $('#f-state'), di = $('#f-dist'), out = $('#f-out');
    const draw = () => {
      const s = st.value; if (!s) { out.innerHTML = ''; return; }
      const d = di.value;
      let ms = D.members.filter(m => m.state === s);
      if (d !== '') ms = ms.filter(m => m.chamber === 'Senate' || String(m.district) === d);
      ms.sort((a, b) => (a.chamber === 'Senate' ? -1 : 1) - (b.chamber === 'Senate' ? -1 : 1) || (a.district || 0) - (b.district || 0));
      out.innerHTML = ms.map(memberCard).join('') || '<p class="muted">No members found.</p>';
    };
    st.onchange = () => {
      const s = st.value;
      const reps = D.members.filter(m => m.state === s && m.chamber === 'House').sort((a, b) => (a.district || 0) - (b.district || 0));
      di.innerHTML = '<option value="">All</option>' + reps.map(r => `<option value="${r.district}">${r.district === 0 ? 'At-large' : 'District ' + r.district} (${esc(r.last)})</option>`).join('');
      di.disabled = !s || reps.length <= 1;
      draw();
    };
    di.onchange = draw;
  }
  function memberCard(m) {
    return `<div class="card">${photo(m, 'avatar')}<div class="who">
      <div class="name"><a href="#/member/${m.id}">${title(m)} ${esc(m.name)}</a> ${partyChip(m)}</div>
      <div class="muted small">${esc(seat(m))} · <span class="act ${m.activity.level}" title="${esc(ACT_DESC[m.activity.level])}">${m.activity.level}</span></div>
      <div class="stances">${DIMS().map(d => chip(m, d, { short: true })).join('')}</div>
      ${m.signature ? `<p class="small" style="margin:8px 0 0">${esc(m.signature)}</p>` : ''}
    </div></div>`;
  }
  function legend() {
    return `<span><i data-s="-2"></i>Strongly for guardrails</span><span><i data-s="-1"></i>Leans guardrails</span><span><i data-s="0"></i>Mixed</span><span><i data-s="1"></i>Leans hands-off</span><span><i data-s="2"></i>Strongly hands-off</span><span><i data-s="none"></i>No public position found</span>`;
  }
  function fightCard(dim) {
    return `<div class="fight"><h3>${esc(dim.label)}</h3><div class="q">${esc(dim.question)}</div>${partyBars(dim)}<a class="more" href="#/fights#${dim.key}">What the labels mean and who is where →</a></div>`;
  }
  function partyBars(dim) {
    const rows = [['D', 'Dem'], ['R', 'GOP']].map(([p, lab]) => {
      const ms = D.members.filter(m => m.party === p);
      const counts = { '-2': 0, '-1': 0, '0': 0, '1': 0, '2': 0, none: 0 };
      ms.forEach(m => { const s = m.positions[dim.key].score; counts[s == null ? 'none' : String(s)]++; });
      const total = ms.length;
      const segs = ['-2', '-1', '0', '1', '2', 'none'].filter(k => counts[k]).map(k => `<span data-s="${k}" style="width:${(100 * counts[k] / total).toFixed(2)}%" title="${esc(scaleLabel(dim, k === 'none' ? null : +k))}: ${counts[k]} of ${total} ${lab === 'Dem' ? 'Democrats' : 'Republicans'}"></span>`).join('');
      return `<div class="bar-row"><div class="lab" title="${lab === 'Dem' ? 'Democrats' : 'Republicans'} (${total})">${lab}</div><div class="bar">${segs}</div></div>`;
    });
    return `<div class="bars">${rows.join('')}</div>`;
  }

  // ---------- fights page (explainers)
  function renderFights() {
    const L = D.landscape || {};
    const ex = L.explainers || {};
    app.innerHTML = `<section class="hero" style="padding-bottom:8px"><h1>The five fights</h1><p class="lede">Congress is not debating "AI" in the abstract. It is fighting over five concrete questions. Here is each one in plain English, what the labels on this site mean, and who is where.</p></section>
      ${DIMS().map(dim => {
        const e = ex[dim.key] || {};
        const top = D.members.filter(m => m.positions[dim.key].score != null && m.positions[dim.key].basis !== 'record');
        const side = s => top.filter(m => m.positions[dim.key].score === s).sort((a, b) => actRank(b) - actRank(a));
        return `<article class="explainer" id="${dim.key}">
          <h2>${esc(dim.label)}</h2>
          <p class="muted">${esc(dim.question)}</p>
          ${e.what ? `<p>${esc(e.what)}</p>` : ''}
          ${e.stakes ? `<p>${esc(e.stakes)}</p>` : ''}
          ${e.recent ? `<div class="notice"><strong>Where it stands (Sept 2026):</strong> ${esc(e.recent)}</div>` : ''}
          ${partyBars(dim)}<div class="legend" style="margin:8px 0 14px">${legend()}</div>
          <div class="cols">${[-2, -1, 0, 1, 2].map(s => `<div><div class="chip" data-s="${s}">${esc(dim.scale[String(s)])}</div><p class="small muted" style="margin:6px 0">${esc((e.labels || {})[String(s)] || '')}</p><ul class="small">${side(s).slice(0, 8).map(m => `<li><a href="#/member/${m.id}">${esc(m.name)}</a> <span class="muted">(${m.party}-${m.state})</span></li>`).join('') || '<li class="muted">Nobody yet on the record here</li>'}${side(s).length > 8 ? `<li><a href="#/members?${dim.key}=${s}">All ${side(s).length} →</a></li>` : ''}</ul></div>`).join('')}</div>
          ${(e.bills || []).length ? `<details><summary>Key bills in this fight</summary>${e.bills.map(b => `<div class="billrow"><div class="lbl">${esc(b.label || '')}</div><div>${esc(b.title || '')}${b.direction ? `<span class="dir ${b.direction}">${dirLabel(b.direction)}</span>` : ''}<div class="small muted">${esc(b.what || '')}${b.url ? ` <a href="${esc(b.url)}" target="_blank" rel="noopener">congress.gov</a>` : ''}</div></div></div>`).join('')}</details>` : ''}
        </article>`;
      }).join('')}`;
    if (location.hash.includes('#', 2)) { const id = location.hash.split('#').pop(); const el = document.getElementById(id); if (el) el.scrollIntoView(); }
  }
  const actRank = m => ({ Leader: 3, Active: 2, Some: 1, Quiet: 0 })[m.activity.level] + (m.activity.n_statements || 0) / 100;
  const dirLabel = d => ({ more_guardrails: 'more guardrails', fewer_rules: 'fewer rules', mixed_or_neutral: 'neutral' }[d] || d);

  // ---------- members table
  const TSTATE = { q: '', chamber: '', party: '', state: '', activity: '', has: '', sort: 'name', dir: 1, stance: {} };
  function mountTable(host, q, opts) {
    Object.assign(TSTATE, { q: q.q || '', chamber: q.chamber || '', party: q.party || '', state: q.state || '', activity: q.activity || '', has: q.has || '', sort: q.sort || 'name', dir: q.dir === '-1' ? -1 : 1, stance: {} });
    DIMS().forEach(d => { if (q[d.key] != null && q[d.key] !== '') TSTATE.stance[d.key] = new Set(q[d.key].split(',')); });
    host.innerHTML = `
      <div class="controls">
        <input type="search" id="t-q" placeholder="Search name, state, or district (e.g. Hawley, Ohio, CA-12)" value="${esc(TSTATE.q)}" aria-label="Search members">
        <div class="seg" role="group" aria-label="Chamber">${['', 'Senate', 'House'].map(c => `<button data-k="chamber" data-v="${c}" class="${TSTATE.chamber === c ? 'on' : ''}">${c || 'Both chambers'}</button>`).join('')}</div>
        <div class="seg" role="group" aria-label="Party">${[['', 'All parties'], ['D', 'Democrats'], ['R', 'Republicans'], ['I', 'Independents']].map(([v, l]) => `<button data-k="party" data-v="${v}" class="${TSTATE.party === v ? 'on' : ''}">${l}</button>`).join('')}</div>
        <select id="t-state" aria-label="State"><option value="">All states</option>${states().map(st => `<option value="${st.code}" ${TSTATE.state === st.code ? 'selected' : ''}>${esc(st.name)}</option>`).join('')}</select>
        <select id="t-act" aria-label="Activity level"><option value="">Any activity level</option>${['Leader', 'Active', 'Some', 'Quiet'].map(a => `<option ${TSTATE.activity === a ? 'selected' : ''}>${a}</option>`).join('')}</select>
        <span class="grow"></span>
        <button id="t-csv" title="Download the current rows as a spreadsheet">Download CSV</button>
        <button id="t-reset">Reset</button>
      </div>
      <div class="filters" id="t-filters"></div>
      <div class="count" id="t-count"></div>
      <div class="table-wrap"><table id="t-table"><thead></thead><tbody></tbody></table></div>
      <div class="mlist" id="t-mlist"></div>`;
    $('#t-q', host).oninput = e => { TSTATE.q = e.target.value; draw(); };
    host.querySelectorAll('.seg button').forEach(b => b.onclick = () => { TSTATE[b.dataset.k] = b.dataset.v; b.parentElement.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); draw(); });
    $('#t-state', host).onchange = e => { TSTATE.state = e.target.value; draw(); };
    $('#t-act', host).onchange = e => { TSTATE.activity = e.target.value; draw(); };
    $('#t-reset', host).onclick = () => { location.hash = '#/members'; if (host.id === 'table-host') mountTable(host, {}, opts); };
    $('#t-csv', host).onclick = () => downloadCsv(filtered());
    drawFilters(host);
    draw();

    function drawFilters(host) {
      const f = $('#t-filters', host);
      f.innerHTML = DIMS().map(d => `<div class="frow"><span class="fl">${esc(d.short)}</span>` + [-2, -1, 0, 1, 2, null].map(s => {
        const key = s == null ? 'none' : String(s);
        const on = TSTATE.stance[d.key] && TSTATE.stance[d.key].has(key);
        return `<span class="chip clickable ${on ? 'on' : ''}" data-fd="${d.key}" data-fs="${key}" data-s="${key}" role="button" tabindex="0" title="Show only members whose ${esc(d.label)} position is: ${esc(scaleLabel(d, s))}">${s == null ? 'No position' : esc(d.scale[key])}</span>`;
      }).join('') + '</div>').join('');
      f.querySelectorAll('.chip[data-fd]').forEach(c => c.onclick = () => {
        const set = TSTATE.stance[c.dataset.fd] || (TSTATE.stance[c.dataset.fd] = new Set());
        if (set.has(c.dataset.fs)) set.delete(c.dataset.fs); else set.add(c.dataset.fs);
        if (!set.size) delete TSTATE.stance[c.dataset.fd];
        c.classList.toggle('on');
        draw();
      });
    }
    function filtered() {
      const q = TSTATE.q.trim().toLowerCase();
      let rows = D.members.filter(m => {
        if (TSTATE.chamber && m.chamber !== TSTATE.chamber) return false;
        if (TSTATE.party && m.party !== TSTATE.party) return false;
        if (TSTATE.state && m.state !== TSTATE.state) return false;
        if (TSTATE.activity && m.activity.level !== TSTATE.activity) return false;
        if (TSTATE.has && m.positions[TSTATE.has] && m.positions[TSTATE.has].score == null) return false;
        for (const k in TSTATE.stance) { const s = m.positions[k].score; if (!TSTATE.stance[k].has(s == null ? 'none' : String(s))) return false; }
        if (q) {
          const hay = `${m.name} ${m.last} ${m.state} ${m.state_name} ${seatShort(m)} ${m.chamber} ${PARTY_NAME[m.party]}`.toLowerCase();
          if (!q.split(/\s+/).every(w => hay.includes(w))) return false;
        }
        return true;
      });
      const k = TSTATE.sort, dir = TSTATE.dir;
      const val = m => {
        if (k === 'name') return m.last + ' ' + m.first;
        if (k === 'seat') return m.state + (m.chamber === 'Senate' ? '-0' : '-' + String(m.district).padStart(2, '0'));
        if (k === 'activity') return -({ Leader: 3, Active: 2, Some: 1, Quiet: 0 })[m.activity.level] * 1000 - m.activity.n_bills_119;
        if (k === 'vote') return m.votes['s2025-363'] || 'zz';
        const p = m.positions[k]; return p && p.score != null ? p.score : 99;
      };
      rows.sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * dir || a.last.localeCompare(b.last); });
      return rows;
    }
    function draw() {
      const rows = filtered();
      $('#t-count', host).textContent = `${rows.length} of ${D.members.length} members` + (rows.length && TSTATE.sort !== 'name' ? ` · sorted by ${TSTATE.sort === 'activity' ? 'activity' : TSTATE.sort === 'seat' ? 'state' : (DIMS().find(d => d.key === TSTATE.sort) || {}).label || TSTATE.sort}` : '');
      const cols = [['name', 'Member'], ['seat', 'State'], ...DIMS().map(d => [d.key, d.short]), ['activity', 'Activity']];
      $('thead', host).innerHTML = `<tr>${cols.map(([k, l]) => `<th data-k="${k}" class="${TSTATE.sort === k ? 'sorted' : ''}" title="Sort by ${esc(l)}">${esc(l)}<span class="arrow">${TSTATE.sort === k ? (TSTATE.dir === 1 ? '▲' : '▼') : '↕'}</span></th>`).join('')}</tr>`;
      host.querySelectorAll('th').forEach(th => th.onclick = () => { if (TSTATE.sort === th.dataset.k) TSTATE.dir = -TSTATE.dir; else { TSTATE.sort = th.dataset.k; TSTATE.dir = 1; } draw(); });
      $('tbody', host).innerHTML = rows.map(m => `<tr>
        <td class="member"><div class="mcell">${photo(m)}<div><div class="nm"><a href="#/member/${m.id}">${esc(m.name)}</a> ${partyChip(m)}${m.pacs && m.pacs.length ? ` <span class="pacmark" title="AI super PAC money in this member's race: ${esc(m.pacs.map(p => (p.kind === 'supported' ? 'backed by ' : 'targeted by ') + p.pac).join('; '))}">$</span>` : ''}</div><div class="sub">${esc(title(m))} · ${m.chamber} · since ${m.first_term}</div></div></div></td>
        <td class="nowrap">${esc(seatShort(m))}</td>
        ${DIMS().map(d => `<td>${chip(m, d, { short: true })}</td>`).join('')}
        <td><span class="act ${m.activity.level}" title="${esc(ACT_DESC[m.activity.level])}: ${m.activity.n_bills_119} related bills this Congress, ${m.activity.n_sponsored_119} sponsored">${m.activity.level}</span></td>
      </tr>`).join('');
      $('#t-mlist', host).innerHTML = rows.slice(0, 200).map(m => `<div class="mrow"><div class="mcell">${photo(m)}<div><div class="nm"><a href="#/member/${m.id}">${esc(m.name)}</a> ${partyChip(m)}</div><div class="sub">${esc(seat(m))} · <span class="act ${m.activity.level}">${m.activity.level}</span></div></div></div>
        <div class="stances">${DIMS().map(d => `<div><span class="k">${esc(d.short)}</span>${chip(m, d, { short: true })}</div>`).join('')}</div></div>`).join('') + (rows.length > 200 ? `<p class="muted small">Showing the first 200 on small screens. Narrow the filters to see more.</p>` : '');
    }
  }
  function downloadCsv(rows) {
    const cols = ['Name', 'Party', 'Chamber', 'State', 'District', 'Activity', ...DIMS().flatMap(d => [d.label + ' (label)', d.label + ' (score -2..2)', d.label + ' (summary)']), 'Senate vote #363 (state AI laws)', 'Profile URL'];
    const line = a => a.map(v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"').join(',');
    const body = rows.map(m => line([m.name, m.party, m.chamber, m.state, m.chamber === 'Senate' ? '' : m.district, m.activity.level, ...DIMS().flatMap(d => { const p = m.positions[d.key]; return [p.label, p.score == null ? '' : p.score, p.summary]; }), m.votes['s2025-363'] || '', location.origin + location.pathname + '#/member/' + m.id]));
    const blob = new Blob(['﻿' + line(cols) + '\n' + body.join('\n')], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'congress-ai-positions.csv'; document.body.appendChild(a); a.click(); a.remove();
  }
  function renderMembers(q) {
    app.innerHTML = `<section class="hero" style="padding-bottom:4px"><h1>Every member of Congress</h1><p class="lede">All ${D.members.length} sitting senators, representatives and delegates. Click a position for the source behind it. Filter by chamber, party, state, or any position.</p></section><div id="table-host"></div>`;
    mountTable($('#table-host'), q, {});
  }

  // ---------- member page
  function renderMember(id) {
    const m = byId[id];
    if (!m) { app.innerHTML = '<p class="loading">Member not found. <a href="#/members">Back to all members</a></p>'; return; }
    document.title = `${m.name}: where they stand on AI`;
    const others = D.members.filter(x => x.state === m.state && x.id !== m.id).sort((a, b) => (a.chamber === 'Senate' ? -1 : 1) - (b.chamber === 'Senate' ? -1 : 1) || (a.district || 0) - (b.district || 0));
    const relBills = m.bills.map(b => ({ ...b, bill: D.bills[b.id] })).filter(b => b.bill).sort((a, b) => (b.bill.congress - a.bill.congress) || ({ major: 0, notable: 1, minor: 2 })[a.bill.significance] - ({ major: 0, notable: 1, minor: 2 })[b.bill.significance] || (b.date || '').localeCompare(a.date || ''));
    const byLane = {};
    relBills.forEach(b => { (byLane[b.bill.lane] = byLane[b.bill.lane] || []).push(b); });
    const LANE = { ai_risk_control: 'AI safety and accountability', data_centers_energy: 'Data centers and energy', preemption_state_laws: 'State AI laws', tech_regulation_broad: 'Big Tech and online rules', kids_online_safety: 'Kids online', deepfakes_likeness_copyright: 'Deepfakes, likeness and copyright', chips_china_export: 'Chips and China', ai_government_research: 'Government AI, research and workforce', workers_jobs: 'AI and jobs' };
    app.innerHTML = `
      <a class="back" href="#/members">← All members</a>
      <section class="member-head">
        ${photo(m)}
        <div class="info">
          <h1>${esc(title(m))} ${esc(m.name)}</h1>
          <div class="meta">${partyChip(m)} <span>${esc(PARTY_NAME[m.party] || '')}</span> · <span>${esc(seat(m))}</span> · <span>In office since ${m.first_term}</span> · <span class="act ${m.activity.level}" title="${esc(ACT_DESC[m.activity.level])}">${m.activity.level} on AI</span></div>
          <div class="meta small" style="margin-top:6px">${m.url ? `<a href="${esc(m.url)}" target="_blank" rel="noopener">Official site</a>` : ''}<a href="https://www.congress.gov/member/${encodeURIComponent(m.name.toLowerCase().replace(/[^a-z ]/g, '').replace(/\s+/g, '-'))}/${m.id}" target="_blank" rel="noopener">congress.gov</a>${m.wikipedia ? `<a href="https://en.wikipedia.org/wiki/${encodeURIComponent(m.wikipedia.replace(/ /g, '_'))}" target="_blank" rel="noopener">Wikipedia</a>` : ''}</div>
          ${m.signature ? `<p class="sig">${esc(m.signature)}</p>` : '<p class="sig muted">No notable public AI activity found beyond the record below.</p>'}
          ${m.quote ? `<blockquote>${esc(m.quote.text)}<cite>${m.quote.date ? fmtDate(m.quote.date) + ' · ' : ''}<a href="${esc(m.quote.url)}" target="_blank" rel="noopener">source</a></cite></blockquote>` : ''}
          ${m.groups && m.groups.length ? `<div class="pill-row small">${m.groups.map(g => `<span class="act">${esc(g)}</span>`).join('')}</div>` : ''}
          ${m.pacs && m.pacs.length ? `<div class="pacbox"><strong>AI money in their race:</strong><ul class="small">${m.pacs.map(p => `<li><span class="pk ${p.kind}">${p.kind === 'supported' ? 'Backed by' : 'Targeted by'}</span> <strong>${esc(p.pac)}</strong>${p.agenda ? ` <span class="muted">(${esc(p.agenda)})</span>` : ''}: ${esc(p.detail)} ${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">source</a>` : ''}</li>`).join('')}</ul></div>` : ''}
          ${m.committees.length ? `<details><summary>Committees (${m.committees.length})</summary><ul class="small">${m.committees.map(c => `<li>${esc(c)}</li>`).join('')}</ul></details>` : ''}
        </div>
      </section>
      <section class="section"><div class="section-head"><h2>Positions</h2><p>Negative-sounding? No: teal simply means "wants more guardrails", orange means "wants a lighter touch". Each card explains the evidence.</p></div>
      <div class="pos-grid">${DIMS().map(d => posCard(m, d)).join('')}</div></section>
      ${Object.keys(m.votes).length ? `<section class="section"><h2>Key votes</h2>${D.votes.filter(v => m.votes[v.id]).map(v => `<div class="votecard"><h3>${esc(v.title)}</h3><p class="muted small">${v.chamber} roll call, ${fmtDate(v.date)}. ${esc(v.plain)}</p><p><strong>${esc(m.last)} voted:</strong> <span class="vote ${voteClass(m.votes[v.id])}">${esc(m.votes[v.id])}</span> <span class="muted">(${esc(m.votes[v.id] === 'Yea' || m.votes[v.id] === 'Aye' || m.votes[v.id] === 'Yes' ? v.yea_means : m.votes[v.id] === 'Nay' || m.votes[v.id] === 'No' ? v.nay_means : 'did not vote')})</span> · <a href="${esc(v.govtrack)}" target="_blank" rel="noopener">full roll call</a></p></div>`).join('')}</section>` : ''}
      <section class="section"><div class="section-head"><h2>Related bills (${relBills.length})</h2><p>Every AI or tech bill this member sponsored or cosponsored in the 118th and 119th Congress, from official congress.gov data.</p></div>
        ${relBills.length ? Object.keys(byLane).map(l => `<h3 style="margin-top:16px">${esc(LANE[l] || l)}</h3>${byLane[l].map(b => `<div class="billrow"><div><div class="lbl"><a href="${esc(b.bill.url)}" target="_blank" rel="noopener">${esc(b.bill.label)}</a></div><div class="lane">${b.bill.congress}th · ${b.role === 'sponsor' ? 'Sponsor' : 'Cosponsor'}</div></div><div><strong>${esc(b.bill.title)}</strong><span class="dir ${b.bill.direction}">${dirLabel(b.bill.direction)}</span><div class="small muted">${esc(b.bill.what)} ${b.bill.n_cosponsors ? `· ${b.bill.n_cosponsors} cosponsors` : ''}${b.bill.enacted ? ' · <strong>became law</strong>' : ''}</div></div></div>`).join('')}`).join('') : '<p class="muted">None found.</p>'}
      </section>
      <section class="section"><h2>Others from ${esc(m.state_name)}</h2><div class="cards">${others.slice(0, 6).map(memberCard).join('')}</div>${others.length > 6 ? `<p><a href="#/state/${m.state}">All ${others.length + 1} members from ${esc(m.state_name)} →</a></p>` : ''}</section>`;
  }
  const voteClass = v => ({ Yea: 'Yea', Aye: 'Aye', Yes: 'Yes', Nay: 'Nay', No: 'No', 'Not Voting': 'NV', Present: 'Present' })[v] || 'NV';
  function posCard(m, d) {
    const p = m.positions[d.key];
    const ev = p.evidence || [];
    const conf = p.score == null ? '' : p.basis === 'record' ? 'Based on bill record only, no statements found' : p.basis === 'letter' ? 'Based on a signed letter or public statement' : `Confidence: ${p.confidence}`;
    return `<div class="pos"><h3><span>${esc(d.label)}</span>${chip(m, d, { lg: true })}</h3>
      <div class="conf">${esc(conf)}</div>
      <p class="summary">${esc(p.summary)}</p>
      ${ev.length ? `<ul class="evidence">${ev.map(e => `<li><span class="et">${esc(ETYPE[e.type] || e.type)}</span>${e.date ? `<span class="muted small">${fmtDate(e.date)}</span>` : ''}<span class="ver ${e.verified}">${esc(VER[e.verified] || '')}</span><div><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a></div>${e.quote ? `<q>${esc(e.quote)}</q>` : ''}${e.what_it_shows ? `<div class="why small">${esc(e.what_it_shows)}</div>` : ''}</li>`).join('')}</ul>` : ''}
    </div>`;
  }

  // ---------- votes page
  function renderVotes() {
    app.innerHTML = `<section class="hero" style="padding-bottom:8px"><h1>Key votes</h1><p class="lede">Roll-call votes where the substance was AI or tech, explained in plain English, with every member's vote.</p></section>
      ${D.votes.map(v => {
        const ms = D.members.filter(m => m.votes[v.id]).sort((a, b) => a.last.localeCompare(b.last));
        const groups = {};
        ms.forEach(m => { (groups[m.votes[v.id]] = groups[m.votes[v.id]] || []).push(m); });
        return `<article class="votecard" id="${v.id}"><h2>${esc(v.title)}</h2><p class="muted">${v.chamber} roll call · ${fmtDate(v.date)} · <a href="${esc(v.govtrack)}" target="_blank" rel="noopener">GovTrack</a>${v.official ? ` · <a href="${esc(v.official)}" target="_blank" rel="noopener">official record</a>` : ''}</p>
          <p>${esc(v.plain)}</p>
          <div class="tally">${Object.entries(v.tally || {}).map(([k, n]) => `<span><span class="vote ${voteClass(k)}">${esc(k)}</span> ${n}</span>`).join('')}</div>
          <p class="small"><strong>${esc(v.yea_means)}</strong> = Yea · <strong>${esc(v.nay_means)}</strong> = Nay</p>
          ${Object.keys(groups).sort().map(k => `<details ${(groups[k].length <= 12) ? 'open' : ''}><summary>${esc(k)} (${groups[k].length})</summary><div class="vlist">${groups[k].map(m => `<div><a href="#/member/${m.id}">${esc(m.name)}</a><span class="muted">${m.party}-${m.state}</span></div>`).join('')}</div></details>`).join('')}
        </article>`;
      }).join('') || '<p class="muted">No key votes loaded yet.</p>'}`;
  }

  // ---------- bills page
  function renderBills() {
    const bills = Object.values(D.bills).filter(b => b.congress === 119).sort((a, b) => b.n_cosponsors - a.n_cosponsors);
    const LANE = { ai_risk_control: 'AI safety and accountability', data_centers_energy: 'Data centers and energy', preemption_state_laws: 'State AI laws', tech_regulation_broad: 'Big Tech and online rules', kids_online_safety: 'Kids online', deepfakes_likeness_copyright: 'Deepfakes, likeness and copyright', chips_china_export: 'Chips and China', ai_government_research: 'Government AI, research and workforce', workers_jobs: 'AI and jobs' };
    let lane = '';
    app.innerHTML = `<section class="hero" style="padding-bottom:8px"><h1>The bills</h1><p class="lede">${bills.length} AI and tech bills introduced in the 119th Congress, each explained in one sentence, sorted by how many members signed on. Cosponsoring a bill is the most common way a member puts a position on paper.</p></section>
      <div class="controls"><select id="b-lane"><option value="">All topics</option>${Object.entries(LANE).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('')}</select><input type="search" id="b-q" placeholder="Search bills" aria-label="Search bills"><span class="count" id="b-count"></span></div><div id="b-list"></div>`;
    const draw = () => {
      const q = $('#b-q').value.trim().toLowerCase();
      const rows = bills.filter(b => (!lane || b.lane === lane) && (!q || (b.title + ' ' + b.what + ' ' + b.label).toLowerCase().includes(q)));
      $('#b-count').textContent = `${rows.length} bills`;
      $('#b-list').innerHTML = rows.slice(0, 300).map(b => `<div class="billrow"><div><div class="lbl"><a href="${esc(b.url)}" target="_blank" rel="noopener">${esc(b.label)}</a></div><div class="lane">${esc(LANE[b.lane] || b.lane)}</div></div><div><strong>${esc(b.title)}</strong><span class="dir ${b.direction}">${dirLabel(b.direction)}</span><div class="small muted">${esc(b.what)} · ${b.sponsor ? esc(b.sponsor.replace(/^(Rep|Sen)\. /, '$1. ')) + ' · ' : ''}${b.n_cosponsors} cosponsors${b.enacted ? ' · <strong>became law</strong>' : ''}</div></div></div>`).join('');
    };
    $('#b-lane').onchange = e => { lane = e.target.value; draw(); };
    $('#b-q').oninput = draw;
    draw();
  }

  // ---------- about
  function renderAbout() {
    const s = D.stats;
    app.innerHTML = `<section class="hero" style="padding-bottom:8px"><h1>How this works</h1><p class="lede">This site was built so that a person with no background in politics or technology can see, in one place, where their own senators and representative stand on AI, and check the receipts.</p></section>
    <div class="prose">
      <h2>What counts as a position</h2>
      <p>Only things a member actually did or said: how they voted, bills they wrote or cosponsored, letters they signed, and their own statements in press releases, hearings, interviews, op-eds and posts. We never guess from party, state, or what "people like them" tend to think. When we found nothing, the site says so: <span class="chip" data-s="none">No public position found</span>.</p>
      <h2>The scale</h2>
      <p>Every question uses the same five-step scale so the colors mean the same thing everywhere. Teal means the member wants more guardrails, rules or limits. Orange means they want a lighter touch. Gray means their record points both ways or they have said they want a balance.</p>
      <div class="scale-demo">${[-2, -1, 0, 1, 2].map(x => `<span class="chip" data-s="${x}">${['Strongly for guardrails', 'Leans guardrails', 'Mixed', 'Leans hands-off', 'Strongly hands-off'][x + 2]}</span>`).join('')}</div>
      <table><thead><tr><th>Question</th><th>Teal end</th><th>Orange end</th></tr></thead><tbody>${DIMS().map(d => `<tr><td><strong>${esc(d.label)}</strong><br><span class="small muted">${esc(d.question)}</span></td><td>${esc(d.scale['-2'])}</td><td>${esc(d.scale['2'])}</td></tr>`).join('')}</tbody></table>
      <h2>Two kinds of labels</h2>
      <p>A solid chip means we found the member's own words or a signed letter, and a fact-checker opened the source to confirm it. A dashed chip marked <span class="chip record" data-s="-1">record <span class="basis-tag">record</span></span> means we found no statements, so the label rests only on which bills they sponsored or cosponsored. Bill records come straight from congress.gov, but signing a bill is a weaker signal than a speech, so treat those labels as a lean, not a conviction.</p>
      <h2>AI money</h2>
      <p>A <span class="pacmark">$</span> next to a name means an AI-industry or AI-safety super PAC has spent money for or against that member, according to Federal Election Commission filings and press reports. The biggest players are Leading the Future (funded by Andreessen Horowitz, OpenAI's Greg Brockman and Joe Lonsdale, which opposes state AI laws) and Public First Action (funded largely by Anthropic, which backs safeguards). Money is context, not a position: members do not control who spends on their behalf.</p>
      <h2>Activity levels</h2>
      <ul>${Object.entries(ACT_DESC).map(([k, v]) => `<li><span class="act ${k}">${k}</span> ${esc(v)}.</li>`).join('')}</ul>
      <h2>Sources</h2>
      <ul>
        <li><strong>Who is in Congress:</strong> the <a href="https://github.com/unitedstates/congress-legislators" target="_blank" rel="noopener">unitedstates/congress-legislators</a> public dataset, which mirrors official House and Senate records, including special-election winners.</li>
        <li><strong>Bills and cosponsors:</strong> the Government Publishing Office's bulk <a href="https://www.govinfo.gov/bulkdata/BILLSTATUS" target="_blank" rel="noopener">BILLSTATUS</a> data for the 118th and 119th Congress, the same data behind congress.gov. ${Object.keys(D.bills).length} bills were judged relevant and sorted into topics with a one-sentence plain-English summary each.</li>
        <li><strong>Votes:</strong> the House Clerk's roll-call records and Senate roll calls via GovTrack.</li>
        <li><strong>Statements:</strong> members' official websites, committee transcripts, letters, and news reports that quote the member directly. A second, independent pass opened every cited page and marked each item as checked, partly supported, or dropped it.</li>
        <li><strong>Photos:</strong> official congressional portraits (public domain) via unitedstates/images; a few recent arrivals from Wikimedia Commons.</li>
      </ul>
      <h2>Limits, honestly</h2>
      <ul>
        <li>Members change their minds, and Congress moves fast. Data was gathered up to ${fmtDate(D.generated)}.</li>
        <li>A member with no statements is not necessarily uninterested. Rank-and-file members often vote and cosponsor without giving speeches. That is why the record-only labels exist.</li>
        <li>Summaries compress nuance. Always read the linked source before quoting a member.</li>
        <li>Two House seats (Florida's 20th and Texas's 23rd) were vacant when this was built, so ${D.members.length} members are listed rather than 541.</li>
      </ul>
      <h2>Report an error</h2>
      <p>If a position is wrong, missing, or out of date, open an issue on the project's GitHub page with a link to the source. Corrections with a primary source get fixed first.</p>
      <h2>Download the data</h2>
      <p>The full dataset is at <a href="data.json">data.json</a>. The Download CSV button on the members table exports whatever you have filtered.</p>
    </div>`;
  }

  // ---------- boot
  const DATA_URL = 'data.json?v=21ad678454';
  fetch(DATA_URL).then(r => r.json()).then(data => {
    D = data;
    D.members.forEach(m => { byId[m.id] = m; });
    $('#foot-updated').textContent = `Data updated ${fmtDate(D.generated)} · ${D.members.length} members · ${Object.keys(D.bills).length} bills · ${D.votes.length} key votes`;
    window.addEventListener('hashchange', route);
    route();
  }).catch(err => { app.innerHTML = `<p class="loading">Could not load data.json (${esc(err.message)}).</p>`; });
})();
