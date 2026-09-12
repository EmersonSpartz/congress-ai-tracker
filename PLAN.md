# Congress AI Tracker: build plan (session 2026-09-12)

Goal: public website tracking all 539 sitting members of Congress on AI and related tech, comprehensive AND readable by a general audience. Deploy to GitHub Pages (never claude.ai links).

## Data backbone (deterministic, official)
- Roster: unitedstates/congress-legislators legislators-current.json (539: 100 sen, 439 house incl. 6 delegates; FL and TX each have 1 vacancy). Committee membership from committee-membership-current.json.
- Bills: govinfo BILLSTATUS bulk XML for 118th + 119th (32,350 bills) -> scratchpad/data/bills_index.json. 2,175 keyword candidates -> classified by workflow wf_227eeefe-ebf (dimension, direction, plain_english, significance).
- Votes: clerk.house.gov XML (House 2024-2026) + GovTrack CSV export (Senate 2024-2026) downloaded to scratchpad/votes/. Key vote confirmed: Senate #363, 2025-07-01, Blackburn amdt striking the 10-year state AI-law moratorium, 99-1 (Tillis lone Nay).
- Photos: unitedstates/images (public domain) + Wikipedia for 15 newest; scratchpad/photos/.

## Research workflows
1. Landscape (wf_1a3e2422-7a5): votes, bills by lane, caucuses, PACs, trackers, recent events (Jan-Sep 2026), data-center politics by region, most-engaged members.
2. Bill classification (wf_227eeefe-ebf): 44 batches x 50.
3. Per-member research: 104 state groups (<=7 members) in scratchpad/data/member_groups.json. Each agent gets the state data-center context + major bill list + the member's deterministic record, finds statements/letters, assigns stances with evidence + URLs.
4. Verification: per member, fetch every evidence URL, confirm it supports the claim; unsupported evidence dropped, stances downgraded.

## Stance model (same axis for every column: guardrails <-> hands off)
Score -2..+2 plus unknown. Dimension labels:
- Data centers: Pause or block | Protect ratepayers first | Mixed | Build, with conditions | Build faster
- AI risk & control: Strict rules now | Targeted guardrails | Mixed | Light touch | Hands off
- Tech regulation (Big Tech, kids, privacy, 230, antitrust): Rein in Big Tech | Targeted rules | Mixed | Light touch | Hands off
- State-law preemption: Let states regulate | Mixed / conditional | One national rule (block states)
- China & chips: Tighten export controls | Mixed | Sell more chips abroad
Activity: Leader / Active / Some / Quiet (from sponsorships, cosponsorships, statements).
Evidence types: vote, sponsor, cosponsor, letter, statement, hearing, pac. Each has date, title, url, quote, verified flag.

## Site
Static, vanilla JS, hash routes for member pages. Sections: hero + stat tiles; find your reps (state/district); the fights explained with party breakdown charts (diverging teal<->orange, gray midpoint; party shown as D/R text only); the big table (filters, sort, search, stance chips with tooltips); member detail; key votes; methodology + download.
Colors: guardrails teal, hands-off orange, validated with dataviz validator in light and dark.
Repo: ~/Downloads/congress-ai-tracker -> github.com/EmersonSpartz/congress-ai-tracker -> https://emersonspartz.github.io/congress-ai-tracker/
Gates: verify.sh, qa-verifier agent, deep review agent, bug-retros entry, Chrome screenshot of deployed page.
