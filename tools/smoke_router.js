// Minimal DOM shim to exercise app.js routing without a browser. Fails (exit 1) if the members filter route does not render rows.
const fs = require('fs'), path = require('path');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', 'data.json'), 'utf8'));
let src = fs.readFileSync(path.join(__dirname, '..', 'docs', 'app.js'), 'utf8');
const WRITES = [];
class El { constructor(tag){ this.tag=tag; this._html=''; this.children=[]; this.dataset={}; this.classList={ toggle(){}, contains(){return false;}, add(){}, remove(){} }; this.style={}; this.attrs={}; }
  set innerHTML(v){ this._html=String(v); WRITES.push(this._html); } get innerHTML(){ return this._html; }
  set textContent(v){ this._html=String(v); WRITES.push(this._html); } get textContent(){ return this._html.replace(/<[^>]+>/g,''); }
  querySelector(){ return new El('div'); } querySelectorAll(){ return []; } getAttribute(k){ return this.attrs[k]; } setAttribute(k,v){ this.attrs[k]=v; }
  appendChild(){} remove(){} click(){} getBoundingClientRect(){ return {left:0,right:0,top:0,bottom:0}; } addEventListener(){} scrollIntoView(){} }
const app = new El('div'); const pop = new El('div'); const foot = new El('p');
global.document = { querySelector: sel => sel === '#app' ? app : sel === '#popover' ? pop : sel === '#foot-updated' ? foot : new El('div'), querySelectorAll: () => [], addEventListener(){}, createElement: t => new El(t), body: new El('body'), documentElement: new El('html'), getElementById: () => null, title: '' };
global.window = { scrollTo(){}, addEventListener(){}, innerWidth: 1200, scrollX: 0, scrollY: 0 };
global.location = { hash: '#/members?ai_risk=-1', origin: 'http://x', pathname: '/' };
global.requestAnimationFrame = fn => fn(); global.setTimeout = fn => fn();
global.fetch = () => Promise.resolve({ json: () => Promise.resolve(data) });
global.URL = { createObjectURL: () => '' }; global.Blob = function(){};
eval(src);
setImmediate(() => {
  const html = WRITES.join('\n');
  const rows = Math.max(...WRITES.map(w => (w.match(/<tr>/g) || []).length));
  const expected = data.members.filter(m => m.positions.ai_risk.score === -1).length;
  const filtered = html.includes(`${expected} of ${data.members.length} members`);
  if (!html.includes('Every member of Congress') || rows !== expected || !filtered) { console.error('smoke: route did not render filtered table', {rows, expected, filtered, head: html.slice(0, 120)}); process.exit(1); }
  // member route
  location.hash = '#/member/' + data.members[0].id; window.__route(); if (!WRITES.join('\n').includes('Positions')) { console.error('smoke: member route failed'); process.exit(1); } console.log('smoke ok', rows, 'rows');
});
