export const meta = {
  name: 'congress-ai-verify-only',
  description: 'Fact-check researched members whose verification agent stalled',
  phases: [{ title: 'Verify', detail: 'one skeptic per member, two URLs per tool call' }],
}
const SP = '/private/tmp/claude-501/-Users-emersonspartz-Downloads/92b5b173-1cd9-4a3a-97d8-a3935dca0db8/scratchpad'
const members = args.members // [{bioguide, name}]; items and scores are in ${SP}/data/verify_items/<bioguide>.json

const VERIFY_SCHEMA = { type: 'object', properties: {
  bioguide: { type: 'string' },
  checks: { type: 'array', items: { type: 'object', properties: {
    url: { type: 'string' },
    verdict: { type: 'string', enum: ['confirmed','partially_supported','unsupported','unreachable','wrong_person'] },
    corrected_quote: { type: ['string','null'] }, corrected_date: { type: ['string','null'] }, note: { type: 'string' } },
    required: ['url','verdict','corrected_quote','corrected_date','note'] } },
  score_objections: { type: 'array', items: { type: 'object', properties: {
    dimension: { type: 'string' }, objection: { type: 'string' }, suggested_score: { type: ['integer','null'] }, suggested_label: { type: ['string','null'] } },
    required: ['dimension','objection','suggested_score','suggested_label'] } } },
  required: ['bioguide','checks','score_objections'] }

phase('Verify')
const results = await parallel(members.map(m => () => agent(`You are a skeptical fact-checker for a public tracker of members of Congress on AI policy. Today is 2026-09-12. For the member below, OPEN every URL listed using Bash: python3 ${SP}/src/research_tools.py fetch <url> --grep '<first 6 words of the quote>' (falls back to the Wayback Machine when a site blocks fetches; WebSearch is NOT available, do not call it; WebFetch may be a second opinion but the verbatim check must come from the fetch output). TIMING RULE: the harness kills an agent that makes no tool call for 3 minutes, so fetch at most 2 URLs per Bash call and never chain long loops.
Verdicts: confirmed = page names this member and supports the claim; quote (if any) appears verbatim or nearly so. partially_supported = right person and topic but the claim or quote overstates it. unsupported = page does not support it, or the quote is not there. unreachable = could not load after retries. wrong_person = the page is about someone else.
If a quote is close but inexact, put the exact text in corrected_quote. Fill corrected_date when the page shows a date the item lacks or gets wrong. Then list objections to the assigned scores. SCALE (NEGATIVE = more guardrails/regulation, POSITIVE = hands-off): data_centers -2 Pause or block, -1 Protect ratepayers first, 0 Mixed, 1 Build with conditions, 2 Build faster; ai_risk -2 Strict rules now, -1 Targeted guardrails, 0 Mixed, 1 Light touch, 2 Hands off; tech_regulation -2 Rein in Big Tech, -1 Targeted rules, 0 Mixed, 1 Light touch, 2 Hands off; preemption -2 Let states regulate, -1 Leans states, 0 Mixed or conditional, 1 Leans national rule, 2 One national rule; china_chips -2 Tighten export controls, -1 Leans hawkish, 0 Mixed, 1 Leans sell more, 2 Sell more chips abroad. Every objection must give suggested_score AND the matching suggested_label from this list. Only object when sources clearly contradict the score or the evidence is too thin. Default when unsure is partially_supported. Output is data for a program.

Member: ${m.name} (${m.bioguide})
FIRST read the file ${SP}/data/verify_items/${m.bioguide}.json with the Read tool: it holds the assigned scores and the list of items to check (dim, type, title, url, quote, what_it_shows). Check every item in it.`,
  { label: `verify:${m.name}`, phase: 'Verify', schema: VERIFY_SCHEMA, effort: 'medium' })))
const ok = results.filter(Boolean)
log(`verified ${ok.length}/${members.length}`)
return { verifications: ok, failed: members.filter((m, i) => !results[i]).map(m => m.name) }
