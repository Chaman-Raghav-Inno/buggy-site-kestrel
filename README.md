# buggy-site-kestrel: Kestrel Works

Kestrel Works is an HR and payroll portal (timesheets, leave requests and balances, expense claims in several
currencies, payslips, a team calendar, a staff directory, a profile with bank details, and a manager's approvals
queue) with **40 functional bugs planted on purpose**, to measure how many the AI QA Scanner finds. It is the fifth
benchmark site, after [buggy-site](https://github.com/Chaman-Raghav-Inno/buggy-site) (Lumen Goods),
[buggy-site-taskline](https://github.com/Chaman-Raghav-Inno/buggy-site-taskline) (Taskline),
[buggy-site-driftwood](https://github.com/Chaman-Raghav-Inno/buggy-site-driftwood) (Driftwood Stays) and
[buggy-site-fernhill](https://github.com/Chaman-Raghav-Inno/buggy-site-fernhill) (Fernhill Academy). Its bugs break
company policies: hour formats, overtime, working days and holidays, carry-over caps, receipt thresholds, mileage
tiers, tax on pay, approval rules, and one access-control hole.

[BUGS.md](BUGS.md) is the answer key: for each bug, the steps to reproduce, what should happen, what happens, its
severity, how hard it is to notice and where it is in the code. The site never serves that file, and nothing it
serves names or hints at a bug. The policies each bug breaks are published on the site (`/help`).

## Run it

```sh
python -m kestrel          # http://localhost:8084 (PORT changes the port)
```

Standard library only (Python 3.11+); no install step.

- Accounts (password `Kestrel@2026`, shown on the login page): `maya@kestrel.test` (employee),
  `leo@kestrel.test` (Maya's manager, who approves the team's requests).
- Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
  other's changes. Both accounts share that copy within one browser, so Leo's approvals show up for Maya. A restart
  or redeploy resets everything.

## Deploy on Railway

New service → GitHub repo → this repository, then **Generate domain** under Networking. `railway.json` sets the
start command and health check (`/healthz`); no variables or volume are needed. Avoid redeploying while a scan runs.

## Development

```sh
pip install ruff pytest
ruff check . && ruff format --check .
pytest -q
```

`tests/test_kestrel.py` keeps the server-side bugs in place and checks that nothing served gives a bug away.
Server-side code marks each bug with a `BUG-nn` comment; the served files must not.
