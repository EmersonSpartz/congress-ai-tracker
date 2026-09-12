# Where Congress Stands on AI

A public tracker of every sitting member of the U.S. Congress and where they stand on five AI questions: AI data centers, AI risk and control, Big Tech regulation, state AI laws (federal preemption), and chips for China. Every position links to a vote, a bill, or the member's own words.

Live site: https://emersonspartz.github.io/congress-ai-tracker/


## What is in the data (as of 2026-09-12)
- 539 sitting members (100 senators, 439 representatives and delegates), all researched individually.
- 7,830 pieces of evidence: 3,759 official votes and bill sponsorships, 3,438 statements confirmed at the source by a second pass, 277 marked partly supported, 276 from signed letters and joint statements.
- 703 AI and tech bills from the 118th and 119th Congress, each with a one-sentence plain-English summary.
- 10 key roll-call votes with every member's vote.
- Activity levels: 85 Leaders, 188 Active, 262 Some, 4 Quiet.

## Pipeline
1. `tools/index_bills.py` indexes govinfo BILLSTATUS bulk XML; `tools/scan_votes2.py` + `tools/index_votes.py` collect roll calls.
2. Agent workflows classify bills, map the landscape (`tools/make_landscape.py` turns that into explainers, PAC money, caucus rosters and signed letters), research every member by state group, and fact-check every cited source (`tools/research_workflow.js`, `tools/verify_only_workflow.js`; agents use `tools/research_tools.py` for Google News RSS, Wayback listings and verbatim page text).
3. `tools/ingest_research.py` writes `source/research/` and `source/verification/`; `build.py` validates every claim against the official record and writes `docs/data.json`.
4. `verify.sh` checks the build, data integrity, the router (Node smoke test) and the deployed site.

## How it is built
- `source/` holds the inputs: the congressional roster (unitedstates/congress-legislators), official bill data (govinfo BILLSTATUS bulk XML for the 118th and 119th Congress), roll-call votes (House Clerk, Senate via GovTrack), agent-classified bill topics, and per-member researched positions with fact-check verdicts.
- `build.py` merges everything into `docs/data.json`.
- `docs/` is a static site (vanilla JS) served by GitHub Pages.
- `verify.sh` checks the build, the data, and the deployed site.

## Report an error
Open an issue with a link to a primary source (the member's own statement, a roll call, or congress.gov). Corrections with primary sources get fixed first.

## License
Code: MIT. Data: CC BY 4.0. Photos are official public-domain congressional portraits; a few are from Wikimedia Commons under their own licenses.
