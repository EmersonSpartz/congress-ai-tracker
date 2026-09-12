# Where Congress Stands on AI

A public tracker of every sitting member of the U.S. Congress and where they stand on five AI questions: AI data centers, AI risk and control, Big Tech regulation, state AI laws (federal preemption), and chips for China. Every position links to a vote, a bill, or the member's own words.

Live site: https://emersonspartz.github.io/congress-ai-tracker/

## How it is built
- `source/` holds the inputs: the congressional roster (unitedstates/congress-legislators), official bill data (govinfo BILLSTATUS bulk XML for the 118th and 119th Congress), roll-call votes (House Clerk, Senate via GovTrack), agent-classified bill topics, and per-member researched positions with fact-check verdicts.
- `build.py` merges everything into `site/data.json`.
- `site/` is a static site (vanilla JS) served by GitHub Pages.
- `verify.sh` checks the build, the data, and the deployed site.

## Report an error
Open an issue with a link to a primary source (the member's own statement, a roll call, or congress.gov). Corrections with primary sources get fixed first.

## License
Code: MIT. Data: CC BY 4.0. Photos are official public-domain congressional portraits; a few are from Wikimedia Commons under their own licenses.
