# Kestrel Works: answer key (40 planted bugs)

Kestrel Works is an HR and payroll portal (timesheets, leave, expenses, payslips, a team calendar, a staff directory,
a profile with bank details, and a manager's approvals queue) with **functional bugs planted on purpose**, for checking
what the AI QA Scanner finds. Most bugs break a company policy published on the site, so finding them takes the
policies, some arithmetic, a second page, a reload or the second account.

This file is never served, and nothing the site serves (pages, scripts, CSS, images) names or hints at a bug.
Server-side code marks each one with a `BUG-nn` comment; `tests/test_kestrel.py` keeps the server-side ones in place.
The rules every bug breaks are published on the site's **Company policies** page (`/help`).

## Run it

- **Locally**: `python -m kestrel` (port 8084, or `PORT`), then open http://localhost:8084.
- **Railway**: New service → GitHub repo → this repository, then **Generate domain**. `railway.json` sets the start
  command and health check; no variables or volume needed.

Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
other's changes. Logging in as Maya and then Leo in the same browser shares one world, so what Leo approves is what
Maya sees. A restart resets everything.

## Test data

Days below are counted from the day the session starts ("day 0" is today, UTC). "Week 0" is the week (Monday to
Sunday) containing today.

| What | Value |
|---|---|
| Accounts (password `Kestrel@2026`, listed on the login page) | `maya@kestrel.test` Maya Okafor, product designer · `leo@kestrel.test` Leo Brandt, Maya's manager (team: Maya, Ravi Patel, Sofia Lindgren, Tomás Ortega, Hana Kim) |
| Maya's timesheets | Week 0: draft, Mon 8 h and Tue 7.5 h on Apollo app · week −1: approved, days 10, 10, 6, 8, 6 h = 40 h · week −2: rejected with a reason ("Friday was at the client, not Training…") · week −3: approved, 42 h |
| Maya's leave | Allowance 25, carried over 8 · approved: 5 days (~3 months ago), 7 days (~2 months ago), Mon–Tue around day 15–21 · pending: one Friday around day 24–30 · correct available balance 15 |
| Team leave | Ravi: approved Mon–Fri around day 3–9 · Hana: pending Tue–Thu around day 7–13 · Tomás: **rejected** Wed–Thu around day 2–8 |
| Public holidays | Founders' Day (a weekday around day 10–12) and Company wellbeing day (around day 38–40), listed on `/help` and the leave page |
| Maya's expenses | Paid: train €42.50 · pending: hotel €180 · rejected: taxi €35 (no receipt) · mileage so far this year: 9,800 km |
| Rates | 1 USD = €0.92 · 1 GBP = €1.17 · 1 JPY = €0.0061 |
| Payslips | The last three months. Maya (salary €48,000, hourly €23.08): ids 1–3, oldest first; id 2 has 4 h overtime and €42.50 expenses · Leo: ids 4–6 |
| Approvals (Leo) | 7 items: Ravi's and Sofia's timesheets for week −1, expenses from Maya (hotel), Ravi (train) and **Leo himself** (client dinner €64), leave from Hana and Maya |
| Directory | 24 people, 8 a page; the earliest starter is Daniel Weiss (Oct 2015) |

Difficulty: **Medium** needs a flow or a comparison; **Hard** needs the published policies, a second page, a reload,
a role switch or an edge-case value; **Expert** needs arithmetic across several numbers or a value converted first.

## The bugs

### Timesheets

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-01 | "7:30" is read as 7.3 hours | Timesheet (week 0): enter `7:30` in a day, Save | 7.5 h (policies: "7:30" is allowed) | Day total "7.3 h"; Save says "Hours go in quarter-hour steps" | High | Hard | `static/timesheet.js` `parse` |
| BUG-02 | Week total leaves out Sunday | Week 0: enter 4 h on Sunday | Week total 19.5 h | 15.5 h (the home page says 19.5) | High | Medium | `static/timesheet.js` `totals` |
| BUG-03 | Overtime is worked out per day | Previous week (week −1): 10, 10, 6, 8, 6 h = 40 h | Overtime 0 h (only hours over 40 a week) | "Overtime 4 h" (hours over 8 each day) | High | Hard | `server.py` `Store.week_view` |
| BUG-04 | A submitted week can still change | Week 0: Submit week (inputs lock), then Copy last week | Refused: the week is locked | "Copied last week's hours"; the submitted week now has last week's hours | Medium | Hard | `server.py` `Store.save_timesheet`, `static/timesheet.js` (Copy stays enabled) |
| BUG-05 | More than 24 hours a day is accepted | Week 0: 25 on Monday, Save | Refused (policies: at most 24) | "Saved."; day total 25 h | Medium | Medium | `server.py` `Store.save_timesheet` |
| BUG-06 | The rejection reason isn't shown | Week −2 (Rejected) | The manager's reason on the week | Only "Rejected"; the reason is never shown | Medium | Hard | `static/timesheet.js` `draw` (shows it only for submitted weeks) |

### Leave

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-07 | The form counts weekends | Request Friday to the following Monday | "This request uses 2 days" | "This request uses 4 days" (the saved request says 2) | Low | Medium | `static/leave.js` `preview` |
| BUG-08 | Public holidays use up leave | Request Monday to Friday of the week with Founders' Day | 4 days | 5 days | High | Hard | `server.py` `working_days` |
| BUG-09 | Overlapping requests are accepted | Request the Friday that's already pending | Refused | "Request sent to your manager"; the day is booked twice | Medium | Medium | `server.py` `Store.request_leave` |
| BUG-10 | Requests beyond the balance are accepted | Request six weeks (30 days) with 18 or fewer left | Refused | Sent; Available goes negative | High | Medium | `server.py` `Store.request_leave` |
| BUG-11 | A half day uses a whole day | Tick "Half day" on a weekday, send | 0.5 day (the form says so) | Recorded as 1 day | High | Hard | `server.py` `Store.request_leave` |
| BUG-12 | Cancelling leave doesn't give the days back | Cancel the approved Mon–Tue leave | Available goes up by 2 | Unchanged | High | Hard | `server.py` `Store.balance` |
| BUG-13 | Carry-over isn't capped at 5 days | Leave page, balance | Carried over 5; Available 15 | Carried over 8 days; Available 18 | High | Expert | `server.py` `Store.balance` |
| BUG-14 | An end date before the start is accepted | First day = day 70, last day = day 66 | Refused | Sent as a 0-day request | Low | Medium | `server.py` `Store.request_leave` |

### Expenses

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-15 | "1,250.00" is claimed as €1 | Hotel, EUR, amount `1,250.00`, with a receipt | €1,250.00 (or a format error) | "Claim submitted: €1.00 to be reimbursed" | High | Hard | `static/expenses.js` (`parseFloat`) |
| BUG-16 | Receipt rule checks the amount before conversion | Travel, GBP 24, no receipt | Refused: £24 is €28.08, over €25 | Accepted (GBP 26 with no receipt is refused) | Medium | Expert | `server.py` `Store.claim` |
| BUG-17 | Meals aren't capped at €50 | Meals, €80, with a receipt | €50.00 reimbursed | €80.00 | Medium | Hard | `server.py` `Store.claim` |
| BUG-18 | Mileage ignores the lower rate after 10,000 km | Mileage, 500 km (9,800 km already this year) | 200 × €0.45 + 300 × €0.25 = €165.00 | €225.00 (all at €0.45) | Medium | Expert | `server.py` `Store.mileage` |
| BUG-19 | Claims older than 90 days are accepted | Any claim dated 120 days ago | Refused | Accepted | Medium | Hard | `server.py` `Store.claim` |
| BUG-20 | Double-clicking Submit claims twice | Fill a claim, double-click Submit claim | One claim | Two identical claims | High | Hard | `static/expenses.js` (button never disabled) |
| BUG-21 | "Awaiting approval" includes rejected claims | Expenses page | €180.00 (the pending hotel) | €215.00 (adds the rejected €35 taxi) | Low | Hard | `server.py` `Store.expense_summary` |

### Payslips

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-22 | Expenses are taxed | Payslip id 2 (4 h overtime, €42.50 expenses) | Income tax 20% of salary + overtime | "Income tax (20% of €4,134.82)": the expenses are included | High | Expert | `server.py` `Store.payslip_view` |
| BUG-23 | Overtime is paid at the plain rate | Payslip id 2: Overtime (4 h), hourly rate €23.08 | 4 × 23.08 × 1.5 = €138.48 | €92.32 | High | Expert | `server.py` `Store.payslip_view` |
| BUG-24 | Payslip CSV breaks on thousands | Download CSV | "4,000.00" quoted, two columns | `Base salary,4,000.00` splits into three columns | Low | Hard | `server.py` `Store.payslip_csv` |
| BUG-25 | "Gross pay this year" leaves out the month | Any payslip, e.g. the oldest | Includes that month (policies) | Previous months only; the first payslip of the year says €0.00 | Medium | Hard | `server.py` `Store.payslip_view` |
| BUG-26 | Anyone's payslip opens by its number | As Maya, open `/payslip?id=4` | Refused (payslips are private) | Leo's payslip: name, salary, net pay | Critical | Hard | `server.py` `Store.payslip` |

### Team calendar

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-27 | The last day of leave isn't shown | Team: Ravi's approved Monday to Friday | Five days marked | Four (Friday missing); one-day leave (Maya's pending Friday) doesn't show at all | Medium | Medium | `static/team.js` (end date treated as exclusive) |
| BUG-28 | Rejected leave is still shown | Team: Tomás | Nothing (his request was rejected) | Two days marked as pending | Low | Medium | `server.py` `Store.team` |

### People and profile

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-29 | Last names don't find anyone | People: search "Okafor" | Maya Okafor (policies: first or last name) | "Nobody matches" ("Maya" works) | Medium | Medium | `server.py` `Store.people` |
| BUG-30 | "Start date" sorts the text, not the date | People, Sort by Start date (earliest first) | Daniel Weiss (Oct 2015) first | Grace Ho (1 Apr 2019), Tomás Ortega (1 Jun 2020)…: sorted by day number | Low | Hard | `server.py` `Store.people` |
| BUG-31 | Next goes past the last page | People: Next until page 3 of 3, Next again | Next disabled | "Page 4 of 3", empty | Low | Medium | `static/people.js` |
| BUG-32 | IBANs with spaces are refused | Profile: Save details with the IBAN as shown ("GB82 WEST 1234…") | Saved (policies: spaces are fine) | "Enter a valid IBAN" | Medium | Medium | `static/profile.js` `IBAN` |
| BUG-33 | Phone changes aren't saved | Profile: change the phone (IBAN without spaces), Save, reload | The new number | "Saved." but the old number comes back | High | Hard | `static/profile.js` (sends `phone_number`), `server.py` `Store.save_profile` |
| BUG-34 | Cancel saves the emergency contact | Profile: Change, type a new name, Cancel | Nothing changes | The new name is saved | Medium | Medium | `pages/profile.html` (Cancel is a submit button) |

### Approvals (Leo)

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-35 | Managers approve their own claims | Approvals: Leo's "Client dinner with Northwind" is in his queue; approve it | Not in the queue (goes to his manager) | Listed; "Approved 1 request" | Critical | Hard | `server.py` `Store.queue` |
| BUG-36 | Select all approves hidden rows | Leave tab, Select all, Approve selected | The 2 leave requests | Every item in every tab is approved ("Approved 5 requests" or similar) | High | Hard | `static/approvals.js` (`#ap-all` selects all items) |
| BUG-37 | Rejecting doesn't need a reason | Select a row, Reject selected, leave the reason empty, Reject | "Enter a reason" | Rejected with no reason | Medium | Medium | `server.py` `Store.decide` |
| BUG-38 | The Approvals count in the menu doesn't update | Approve or reject anything | The badge goes down | Still 7 until the page is reloaded | Low | Medium | `server.py` `render` / `static/approvals.js` |

### Home and errors

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-39 | Home shows more leave than the leave page | Home "Leave left" vs Leave "Available" | Same number (15) | Home 21 (ignores booked and pending), Leave 18 | Medium | Hard | `server.py` `Store.home` |
| BUG-40 | An unknown payslip hangs on "Loading…" | Open `/payslip?id=999` | "We couldn't find that payslip" | "Loading…" forever and a JavaScript error | Low | Medium | `static/payslip.js` (no check on the response) |

## What is not a planted bug

- Console errors that come with a bug: 400 when saving "7:30" (BUG-01), 404 and the JavaScript error on an unknown
  payslip (BUG-40), 403 on `/approvals` as Maya, 404 on unknown pages.
- Bugs that combine: BUG-13 also inflates BUG-39's numbers; BUG-22 and BUG-23 both change payslip id 2.
- Date pickers show dates in the browser's format.
- Each visitor has a private world: changes in one browser session do not show in another.
- "Demo HR portal for QA testing" in the footer and the demo accounts on the login page.

By area: timesheets 6, leave 8, expenses 7, payslips 5, team calendar 2, people and profile 6, approvals 4, home and
errors 2.
By difficulty: Medium 15, Hard 20, Expert 5. By severity: Critical 2, High 14, Medium 15, Low 9.
