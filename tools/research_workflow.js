export const meta = {
  name: 'congress-ai-member-research',
  description: 'Research and verify every member of Congress on AI data centers, AI risk, tech regulation, preemption and chips, one state group at a time',
  phases: [{ title: 'Research', detail: 'one agent per state group of up to 7 members' }, { title: 'Verify', detail: 'one skeptic per member, opens every source' }],
}

const SP = '/private/tmp/claude-501/-Users-emersonspartz-Downloads/92b5b173-1cd9-4a3a-97d8-a3935dca0db8/scratchpad'
const groups = args.groups // array of {index, state, part, of, members:[{bioguide,name}]}

const EVIDENCE = { type: 'object', properties: {
  type: { type: 'string', enum: ['vote','sponsor','cosponsor','letter','statement','hearing','interview','op_ed','social_post','pac','other'] },
  date: { type: ['string','null'], description: 'YYYY-MM-DD or YYYY-MM or null' },
  title: { type: 'string', description: 'what this is, e.g. "Press release: Hawley introduces AI Risk Evaluation Act"' },
  url: { type: 'string' },
  quote: { type: ['string','null'], description: 'verbatim words from the source, 40 words max, or null' },
  what_it_shows: { type: 'string', description: 'one plain sentence on why this matters for the stance' } },
  required: ['type','title','url','quote','what_it_shows'] }

const POSITION = { type: 'object', properties: {
  score: { type: ['integer','null'], description: '-2, -1, 0, 1, 2 or null for no public position' },
  confidence: { type: 'string', enum: ['high','medium','low','none'] },
  summary: { type: 'string', description: 'one or two plain sentences for a general reader; if null score, say what you looked for and did not find' },
  evidence: { type: 'array', items: EVIDENCE } },
  required: ['score','confidence','summary','evidence'] }

const MEMBER = { type: 'object', properties: {
  bioguide: { type: 'string' }, name: { type: 'string' },
  positions: { type: 'object', properties: {
    data_centers: POSITION, ai_risk: POSITION, tech_regulation: POSITION, preemption: POSITION, china_chips: POSITION },
    required: ['data_centers','ai_risk','tech_regulation','preemption','china_chips'] },
  signature: { type: 'string', description: 'one line: what this member is known for on AI/tech, or "No notable public AI activity found"' },
  notable_quote: { type: ['object','null'], properties: { text: { type: 'string' }, date: { type: ['string','null'] }, url: { type: 'string' } }, required: ['text','url'] },
  groups: { type: 'array', items: { type: 'string' }, description: 'AI caucus / task force / working group memberships and relevant committee leadership roles found' },
  search_notes: { type: 'string' } },
  required: ['bioguide','name','positions','signature','notable_quote','groups','search_notes'] }

const RESEARCH_SCHEMA = { type: 'object', properties: { members: { type: 'array', items: MEMBER } }, required: ['members'] }

const RUBRIC = `You are building a public, plain-English tracker of where every member of Congress stands on AI. Today is 2026-09-12. You will research a small group of members from one state. Be exhaustive for each member: search their official press releases (site:NAME.senate.gov or site:NAME.house.gov with terms like "artificial intelligence", "AI", "data center", "chatbot", "deepfake", "Big Tech", "Section 230", "export controls", "Nvidia", "preemption", "state AI laws"), local newspapers, hearing remarks, letters, op-eds, interviews, town halls, X/Twitter posts reported in press, and campaign statements. Also search the member's name together with "data center" and "electricity" or "power bills". Use at least 8 distinct searches per member; more for senators and committee leaders.

FILES TO READ FIRST (with the Read tool):
1. The group file: it lists the members and, for each, their VERIFIED record from official data: how they voted on the July 1, 2025 Senate roll call #363 (Blackburn amendment striking the 10-year moratorium on state AI laws from H.R. 1; 99 Yea, 1 Nay), and every relevant bill they sponsored or cosponsored in the 118th and 119th Congress with its dimension and direction. Treat this record as true and cite it as evidence (type sponsor/cosponsor/vote, url = https://www.congress.gov/bill/119th-congress/house-bill/NUMBER or senate-bill/NUMBER; for the vote use https://www.govtrack.us/congress/votes/119-2025/s363).
2. The state context file: the state's data center politics and members already found on record.
3. The top-bills file: the main bills in each lane, so you recognise them.

THE FIVE DIMENSIONS AND SCORES (negative = more guardrails, positive = more hands-off; null = no public position found):
data_centers: -2 Pause or block (moratorium, opposes new projects) | -1 Protect ratepayers first (build only with strong protections for electric bills, water, communities; mostly critical) | 0 Mixed or balanced | 1 Build, with conditions (supportive of growth, acknowledges costs, wants some conditions) | 2 Build faster (permitting reform, federal land, celebrates projects, opposes limits).
ai_risk: -2 Strict rules now (treats advanced AI as a major or existential danger; wants binding safety testing, licensing, liability, or a pause) | -1 Targeted guardrails (supports specific rules: kids and chatbots, deepfakes, transparency, whistleblowers, liability, jobs reporting) | 0 Mixed | 1 Light touch (innovation and beating China first; voluntary standards; skeptical of new mandates) | 2 Hands off (opposes AI regulation, accelerationist, wants to block regulators).
tech_regulation: -2 Rein in Big Tech (break-ups, repeal Section 230, strong privacy law, aggressive antitrust) | -1 Targeted rules (kids online safety, privacy, app store rules, robocalls, specific fixes) | 0 Mixed | 1 Light touch (prefers self-regulation, worried about over-regulation) | 2 Hands off.
preemption: -2 Let states regulate (opposes federal preemption or moratorium on state AI laws) | -1 Leans against preemption or wants a federal law first with states preserved | 0 Mixed or conditional (would accept preemption only with strong federal rules) | 1 Leans toward one national standard | 2 One national rule (supports preempting or pausing state AI laws). NOTE: nearly every senator voted Yea on roll call #363 after the deal collapsed, including Sen. Cruz who wrote the moratorium; a Yea vote alone is NOT evidence of opposing preemption unless the member also said so. Use statements, letters, cosponsorship (e.g. States' Right to Regulate AI Act, GUARDRAILS Act = against preemption; SANDBOX Act, American AI Leadership and Uniformity Act = for preemption) and the Dec 2025 executive order reactions.
china_chips: -2 Tighten export controls (Chip Security Act, GAIN AI, opposes Nvidia H20/H200 sales to China) | -1 Leans hawkish | 0 Mixed | 1 Leans toward selling more chips abroad / lighter controls | 2 Sell more chips abroad (opposes controls, backs the H20/H200 sales, deregulate BIS).

RULES
- Never infer a position from party, state, or vibes. Every non-null score needs at least one evidence item with a URL you actually opened. A single cosponsorship of a minor bill supports at most confidence low.
- Quotes must be VERBATIM from the opened page, 40 words max. If you only saw a summary, set quote null and describe in what_it_shows.
- Prefer the member's own words (press release, floor speech, letter, op-ed) over reporters' characterisations.
- Include contradictory evidence too, and let the summary say "mixed" when it is.
- Do not skip a member. If you truly find nothing beyond the record, give null scores where there is no evidence, keep the record-based evidence, and write an honest summary like "No public statements found on data centers as of Sept 2026."
- No em dashes anywhere in your text. Plain words. Short sentences.
- Also capture: AI caucus / task force memberships, committee chair or ranking roles relevant to AI, and any AI super PAC support or attacks (Leading the Future, Public First) you run into (type pac).
- Your final output is data for a program. Return one member object for each member in the group file, in the same order.`

const VERIFY_SCHEMA = { type: 'object', properties: {
  bioguide: { type: 'string' },
  checks: { type: 'array', items: { type: 'object', properties: {
    url: { type: 'string' },
    verdict: { type: 'string', enum: ['confirmed','partially_supported','unsupported','unreachable','wrong_person'] },
    corrected_quote: { type: ['string','null'], description: 'the verbatim text if the original quote was close but inexact; null otherwise' },
    corrected_date: { type: ['string','null'] },
    note: { type: 'string' } }, required: ['url','verdict','corrected_quote','corrected_date','note'] } },
  score_objections: { type: 'array', items: { type: 'object', properties: {
    dimension: { type: 'string' }, objection: { type: 'string' }, suggested_score: { type: ['integer','null'] } }, required: ['dimension','objection','suggested_score'] } } },
  required: ['bioguide','checks','score_objections'] }

phase('Research')
const researched = await pipeline(groups,
  g => agent(`${RUBRIC}

Group file: ${SP}/data/group_files/group_${String(g.index).padStart(3,'0')}.json
State context file: ${SP}/data/state_context/${g.state}.md
Top bills file: ${SP}/data/top_bills_context.md
State: ${g.state}, part ${g.part} of ${g.of}. Members: ${g.members.map(m => m.name).join('; ')}.`,
    { label: `research:${g.state}-${g.part}`, phase: 'Research', schema: RESEARCH_SCHEMA }),
  async (res, g) => {
    if (!res || !res.members) { log(`research failed for ${g.state}-${g.part}`); return null }
    const verified = await parallel(res.members.map(m => () => {
      const items = []
      for (const [dim, p] of Object.entries(m.positions || {})) for (const e of (p.evidence || [])) if (!['sponsor','cosponsor','vote'].includes(e.type)) items.push({ dim, ...e })
      if (m.notable_quote && m.notable_quote.url) items.push({ dim: 'notable_quote', type: 'statement', title: 'notable quote', url: m.notable_quote.url, quote: m.notable_quote.text, what_it_shows: 'headline quote' })
      if (!items.length) return Promise.resolve({ bioguide: m.bioguide, checks: [], score_objections: [] })
      return agent(`You are a skeptical fact-checker for a public tracker of members of Congress on AI policy. Today is 2026-09-12. For the member below, OPEN every URL listed (WebFetch; if it fails, retry once, then try a WebSearch for the exact quote to find a mirror) and decide whether the page really supports the claim.
Verdicts: confirmed = page names this member and supports the claim; quote (if any) appears verbatim or nearly so. partially_supported = page is about the right person and topic but the claim or quote overstates it. unsupported = page does not support it, or the quote is not there. unreachable = could not load after retries and no mirror found. wrong_person = the page is about someone else.
If a quote is close but inexact, put the exact text in corrected_quote. If the page gives a date the item lacks or has wrong, fill corrected_date. Then, having read the sources, list any objection to the assigned scores (for example "the source shows the member SUPPORTS federal preemption; score should be +2"). Be strict; the default when unsure is partially_supported, not confirmed. Output is data for a program.

Member: ${m.name} (${m.bioguide})
Assigned scores: ${JSON.stringify(Object.fromEntries(Object.entries(m.positions || {}).map(([k, v]) => [k, v.score])))}
Items to check:
${items.map((e, i) => `${i + 1}. [${e.dim} / ${e.type}] ${e.title}\n   URL: ${e.url}\n   Quote: ${e.quote || '(none)'}\n   Claim: ${e.what_it_shows}`).join('\n')}`,
        { label: `verify:${m.name}`, phase: 'Verify', schema: VERIFY_SCHEMA, effort: 'medium' })
    }))
    return { group: `${g.state}-${g.part}`, members: res.members, verification: verified }
  })

const ok = researched.filter(Boolean)
log(`groups done ${ok.length}/${groups.length}; members ${ok.reduce((n, r) => n + r.members.length, 0)}`)
return { groups: ok, failed: groups.filter((g, i) => !researched[i]).map(g => `${g.state}-${g.part}`) }
