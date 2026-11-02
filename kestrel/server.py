"""Kestrel Works: an HR and payroll portal with planted functional bugs, for checking what the AI QA Scanner finds.

The bugs are listed in BUGS.md (the answer key), which is never served. Comments marking a planted bug (BUG-nn)
only appear in server-side code; the pages and scripts the scanner reads carry none.

Each visitor (cookie) gets a private copy of the demo world, kept in memory, so parallel scans never see each
other's changes. Logging in as the employee or the manager in the same browser shares that world.
"""

import datetime as dt
import hmac
import html
import json
import os
import re
import secrets
import threading
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from . import data

HERE = Path(__file__).resolve().parent
PAGES_DIR = HERE / "pages"
STATIC_DIR = HERE / "static"
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    ),
}
MAX_BODY = 1024 * 1024
MAX_SESSIONS = 1500
PEOPLE_PAGE = 8
CALENDAR_DAYS = 28

# path -> (page, title, who may open it)
PAGES = {
    "/": ("landing", "Welcome", None),
    "/login": ("login", "Log in", None),
    "/help": ("help", "Policies", None),
    "/home": ("home", "Home", "user"),
    "/timesheet": ("timesheet", "Timesheet", "user"),
    "/leave": ("leave", "Leave", "user"),
    "/expenses": ("expenses", "Expenses", "user"),
    "/payslips": ("payslips", "Payslips", "user"),
    "/payslip": ("payslip", "Payslip", "user"),
    "/team": ("team", "Team calendar", "user"),
    "/people": ("people", "People", "user"),
    "/profile": ("profile", "Profile", "user"),
    "/approvals": ("approvals", "Approvals", "manager"),
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _text(body: dict, key: str, limit: int = 200) -> str:
    value = body.get(key, "")
    return value.strip()[:limit] if isinstance(value, str) else ""


def _date(value, message: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise ApiError(400, message) from None


def _number(value, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ApiError(400, message)
    return float(value)


def money(x: float) -> float:
    return round(x + 1e-9, 2)


def money_label(x: float) -> str:
    return f"€{x:,.2f}"


def working_days(start: dt.date, end: dt.date, holidays: set[str]) -> int:
    days, day = 0, start
    while day <= end:
        if day.weekday() < 5:  # BUG-08: public holidays are counted as leave days
            days += 1
        day += dt.timedelta(days=1)
    return days


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: OrderedDict[str, dict] = OrderedDict()

    def session(self, sid: str | None) -> tuple[str, dict]:
        if sid and sid in self.sessions:
            self.sessions.move_to_end(sid)
            return sid, self.sessions[sid]
        sid = secrets.token_urlsafe(24)
        self.sessions[sid] = {"world": None, "user": None}
        while len(self.sessions) > MAX_SESSIONS:
            self.sessions.popitem(last=False)
        return sid, self.sessions[sid]

    @staticmethod
    def world(sess: dict) -> dict:
        if sess["world"] is None:
            sess["world"] = data.world(today())
        return sess["world"]

    def user(self, sess: dict) -> dict | None:
        if sess["user"] is None:
            return None
        w = self.world(sess)
        u = next((u for u in w["users"] if u["id"] == sess["user"]), None)
        return u and u | {"person": self.person(w, u["person"])}

    def signed_in(self, sess: dict, manager: bool = False) -> tuple[dict, dict]:
        user = self.user(sess)
        if not user:
            raise ApiError(401, "Please log in.")
        if manager and not user["manager"]:
            raise ApiError(403, "That is for managers.")
        return self.world(sess), user

    @staticmethod
    def person(w: dict, pid: int) -> dict:
        found = next((p for p in w["people"] if p["id"] == pid), None)
        if not found:
            raise ApiError(404, "We couldn't find that person.")
        return found

    def me(self, sess: dict) -> dict:
        user = self.user(sess)
        if not user:
            return {"user": None, "today": self.world(sess)["today"]}
        p = user["person"]
        return {"user": {"id": p["id"], "name": p["name"], "email": user["email"], "manager": user["manager"]},
                "today": self.world(sess)["today"]}  # fmt: skip

    def login(self, sess: dict, body: dict) -> dict:
        w = self.world(sess)
        email = _text(body, "email").lower()
        u = next((u for u in w["users"] if u["email"] == email), None)
        password = body.get("password")
        if not (u and isinstance(password, str)) or not hmac.compare_digest(
            u["hash"], data.password_hash(password, bytes.fromhex(u["salt"]))
        ):
            raise ApiError(401, "Incorrect email or password.")
        sess["user"] = u["id"]
        return self.me(sess)

    # people and profile

    @staticmethod
    def card(p: dict) -> dict:
        start = dt.date.fromisoformat(p["start"])
        keys = ("id", "name", "title", "department", "email", "phone")
        return {k: p[k] for k in keys} | {"start": p["start"], "start_label": f"{start.day} {start:%b %Y}"}

    def people(self, sess: dict, query: dict) -> dict:
        w, _ = self.signed_in(sess)
        arg = {k: (query.get(k) or [""])[0] for k in query}
        q = arg.get("q", "").strip().lower()
        found = [p for p in w["people"] if not q or p["name"].lower().startswith(q)]  # BUG-29: first names only
        if arg.get("department"):
            found = [p for p in found if p["department"] == arg["department"]]
        cards = [self.card(p) for p in found]
        if arg.get("sort") == "start":
            cards.sort(key=lambda c: c["start_label"])  # BUG-30: sorts the label text, not the date
        else:
            cards.sort(key=lambda c: c["name"])
        try:
            page = max(1, int(arg.get("page") or 1))
        except ValueError:
            raise ApiError(400, "Bad page.") from None
        pages = max(1, -(-len(cards) // PEOPLE_PAGE))
        start = (page - 1) * PEOPLE_PAGE
        return {"people": cards[start : start + PEOPLE_PAGE], "page": page, "pages": pages, "total": len(cards)}

    def profile(self, sess: dict) -> dict:
        _, user = self.signed_in(sess)
        p = user["person"]
        keys = ("name", "title", "department", "phone", "iban", "emergency")
        return {k: p[k] for k in keys} | {"email": user["email"], "start": p["start"]}

    def save_profile(self, sess: dict, body: dict) -> dict:
        _, user = self.signed_in(sess)
        p = user["person"]
        if "phone" in body:  # BUG-33: the page sends phone_number, so phone changes are dropped
            phone = _text(body, "phone", 40)
            if not re.fullmatch(r"\+?[\d ()-]{7,20}", phone):
                raise ApiError(400, "Enter a phone number.")
            p["phone"] = phone
        iban = re.sub(r"\s", "", _text(body, "iban", 60)).upper()
        if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
            raise ApiError(400, "Enter a valid IBAN.")
        p["iban"] = " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))
        return self.profile(sess)

    def save_emergency(self, sess: dict, body: dict) -> dict:
        _, user = self.signed_in(sess)
        user["person"]["emergency"] = {"name": _text(body, "name", 80), "phone": _text(body, "phone", 40)}
        return self.profile(sess)

    # timesheets

    def week_view(self, w: dict, uid: int, monday: dt.date) -> dict:
        sheet = w["timesheets"].get(uid, {}).get(monday.isoformat())
        sheet = sheet or {"hours": {p: [0] * 7 for p in data.PROJECTS}, "status": "draft", "comment": ""}
        daily = [sum(sheet["hours"][p][i] for p in data.PROJECTS) for i in range(7)]
        overtime = sum(max(0, h - 8) for h in daily)  # BUG-03: the policy is hours over 40 in the week
        return {
            "week": monday.isoformat(),
            "days": [(monday + dt.timedelta(days=i)).isoformat() for i in range(7)],
            "projects": data.PROJECTS,
            "hours": sheet["hours"],
            "status": sheet["status"],
            "comment": sheet["comment"],
            "total": sum(daily),
            "overtime": overtime,
            "prev": (monday - dt.timedelta(weeks=1)).isoformat(),
            "next": (monday + dt.timedelta(weeks=1)).isoformat(),
            "this": data.monday(dt.date.fromisoformat(w["today"])).isoformat(),
        }

    def timesheet(self, sess: dict, week: str) -> dict:
        w, user = self.signed_in(sess)
        day = _date(week, "Choose a week.") if week else dt.date.fromisoformat(w["today"])
        return self.week_view(w, user["person"]["id"], data.monday(day))

    def save_timesheet(self, sess: dict, week: str, body: dict) -> dict:
        w, user = self.signed_in(sess)
        monday = data.monday(_date(week, "Choose a week."))
        sheets = w["timesheets"].setdefault(user["person"]["id"], {})
        sheet = sheets.get(monday.isoformat())
        if sheet and sheet["status"] == "approved":  # BUG-04: submitted weeks should be locked too
            raise ApiError(409, "This week is locked.")
        given = body.get("hours")
        if not isinstance(given, dict):
            raise ApiError(400, "Send the hours.")
        hours = {}
        for p in data.PROJECTS:
            row = given.get(p, [0] * 7)
            if not isinstance(row, list) or len(row) != 7:
                raise ApiError(400, "Send seven days for each project.")
            clean = []
            for h in row:
                h = _number(h, "Hours must be numbers.")
                if h < 0 or abs(h * 4 - round(h * 4)) > 1e-9:  # BUG-05: no 24-hour limit per day
                    raise ApiError(400, "Hours go in quarter-hour steps from 0.")
                clean.append(h)
            hours[p] = clean
        if sheet is None:
            sheet = sheets[monday.isoformat()] = {"status": "draft", "comment": ""}
        sheet["hours"] = hours
        if sheet["status"] == "rejected":
            sheet["status"] = "draft"
        return self.week_view(w, user["person"]["id"], monday)

    def submit_timesheet(self, sess: dict, week: str) -> dict:
        w, user = self.signed_in(sess)
        monday = data.monday(_date(week, "Choose a week."))
        sheet = w["timesheets"].get(user["person"]["id"], {}).get(monday.isoformat())
        if not sheet or sheet["status"] != "draft":
            raise ApiError(409, "Save some hours on this week first.")
        if not any(any(row) for row in sheet["hours"].values()):
            raise ApiError(400, "Enter your hours before submitting.")
        sheet["status"] = "submitted"
        return self.week_view(w, user["person"]["id"], monday)

    # leave

    def balance(self, w: dict, uid: int) -> dict:
        b = w["balances"][uid]
        mine = [r for r in w["leave"] if r["user"] == uid]
        used = sum(r["days"] for r in mine if r["status"] != "rejected")  # BUG-12: cancelled leave still counts
        carried = b["carried"]  # BUG-13: carry-over is capped at 5 days
        return {"allowance": b["allowance"], "carried": carried, "used": used,
                "available": b["allowance"] + carried - used}  # fmt: skip

    def leave(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        uid = user["person"]["id"]
        mine = sorted((r for r in w["leave"] if r["user"] == uid), key=lambda r: r["start"], reverse=True)
        return {"balance": self.balance(w, uid), "requests": mine, "holidays": w["holidays"], "today": w["today"]}

    def request_leave(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess)
        uid = user["person"]["id"]
        start = _date(body.get("start"), "Choose a start date.")
        end = _date(body.get("end") or body.get("start"), "Choose an end date.")
        if start < dt.date.fromisoformat(w["today"]):
            raise ApiError(400, "Leave can't start in the past.")
        # BUG-14: an end date before the start isn't refused (the request is for 0 days)
        half = bool(body.get("half"))
        if half and end != start:
            raise ApiError(400, "A half day is a single day.")
        days = working_days(start, end, {h["date"] for h in w["holidays"]})  # BUG-11: a half day counts as 1
        if start.weekday() >= 5 and start == end:
            raise ApiError(400, "That day is a weekend.")
        # BUG-09: overlapping requests are not refused
        # BUG-10: requests beyond the available balance are not refused
        r = {"id": w["next_id"], "user": uid, "start": start.isoformat(), "end": end.isoformat(), "days": days,
             "status": "pending", "kind": "Holiday", "half": half, "note": _text(body, "note", 300), "reason": "",
             "created": w["today"]}  # fmt: skip
        w["next_id"] += 1
        w["leave"].append(r)
        return self.leave(sess)

    def cancel_leave(self, sess: dict, rid: int) -> dict:
        w, user = self.signed_in(sess)
        r = next((r for r in w["leave"] if r["id"] == rid and r["user"] == user["person"]["id"]), None)
        if not r:
            raise ApiError(404, "We couldn't find that request.")
        if r["status"] not in ("pending", "approved") or r["start"] <= w["today"]:
            raise ApiError(409, "Only upcoming leave can be cancelled.")
        r["status"] = "cancelled"
        return self.leave(sess)

    def team(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        me = user["person"]
        lead = me["id"] if user["manager"] else me["manager"]
        members = [p for p in w["people"] if p["id"] == lead or p["manager"] == lead]
        start = data.monday(dt.date.fromisoformat(w["today"]))
        days = [(start + dt.timedelta(days=i)).isoformat() for i in range(CALENDAR_DAYS)]
        rows = []
        for p in members:
            absences = [
                {"start": r["start"], "end": r["end"], "status": r["status"], "half": r["half"]}
                for r in w["leave"]
                if r["user"] == p["id"] and r["status"] != "cancelled"  # BUG-28: rejected leave still shows
            ]
            rows.append({"id": p["id"], "name": p["name"], "title": p["title"], "absences": absences})
        return {"days": days, "today": w["today"], "people": rows, "holidays": w["holidays"]}

    # expenses

    @staticmethod
    def mileage(km: float, driven_before: float) -> float:
        return money(km * data.MILEAGE[0][1])  # BUG-18: the lower rate applies after 10,000 km a year

    def expense_summary(self, w: dict, uid: int) -> dict:
        mine = [e for e in w["expenses"] if e["user"] == uid]
        pending = sum(e["reimbursable"] for e in mine if e["status"] != "paid" and e["status"] != "approved")
        approved = sum(e["reimbursable"] for e in mine if e["status"] == "approved")
        # BUG-21: rejected claims are added to the pending total
        return {"pending": money(pending), "approved": money(approved),
                "mileage_km": w["balances"][uid]["mileage_km"]}  # fmt: skip

    def expenses(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        uid = user["person"]["id"]
        mine = sorted((e for e in w["expenses"] if e["user"] == uid), key=lambda e: (e["date"], e["id"]), reverse=True)
        return {"claims": mine, "summary": self.expense_summary(w, uid), "rates": data.RATES, "today": w["today"]}

    def claim(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess)
        uid = user["person"]["id"]
        on = _date(body.get("date"), "Choose the date of the expense.")
        now = dt.date.fromisoformat(w["today"])
        if on > now:
            raise ApiError(400, "The date can't be in the future.")
        # BUG-19: claims older than 90 days are not refused
        category = body.get("category")
        if category not in data.CATEGORIES:
            raise ApiError(400, "Choose a category.")
        description = _text(body, "description", 140)
        if not description:
            raise ApiError(400, "Describe the expense.")
        receipt = _text(body, "receipt", 120)
        if category == "Mileage":
            km = _number(body.get("km"), "Enter the distance in km.")
            if not 0 < km <= 2000:
                raise ApiError(400, "Enter the distance in km (up to 2,000).")
            driven = w["balances"][uid]["mileage_km"]
            currency, amount, eur = "EUR", 0.0, self.mileage(km, driven)
            reimbursable = eur
            w["balances"][uid]["mileage_km"] = driven + km
        else:
            km = 0
            currency = body.get("currency")
            if currency not in data.RATES:
                raise ApiError(400, "Choose a currency.")
            amount = _number(body.get("amount"), "Enter the amount.")
            if not 0 < amount <= 1_000_000:
                raise ApiError(400, "Enter the amount.")
            eur = money(amount * data.RATES[currency])
            if amount > data.RECEIPT_OVER and not receipt:  # BUG-16: compares the amount before conversion
                raise ApiError(400, "Attach a receipt for anything over €25.")
            reimbursable = eur  # BUG-17: meals are capped at €50 a claim
        e = {"id": w["next_id"], "user": uid, "date": on.isoformat(), "category": category,
             "description": description, "currency": currency, "amount": amount, "km": km, "eur": eur,
             "reimbursable": reimbursable, "receipt": receipt, "status": "pending", "reason": "",
             "submitted": w["today"]}  # fmt: skip
        w["next_id"] += 1
        w["expenses"].append(e)
        return self.expenses(sess)

    # payslips

    def payslip_view(self, w: dict, slip: dict) -> dict:
        person = self.person(w, slip["user"])
        base = money(person["salary"] / 12)
        hourly = money(person["salary"] / data.HOURS_A_YEAR)
        overtime = money(slip["overtime_hours"] * hourly)  # BUG-23: overtime is paid at 1.5 times the rate
        gross = money(base + overtime + slip["expenses"])
        taxable = money(base + overtime + slip["expenses"])  # BUG-22: expenses are not taxable
        tax = money(taxable * data.TAX_RATE)
        pension = money(base * data.PENSION_RATE)
        mine = [s for s in w["payslips"] if s["user"] == slip["user"] and s["period"][:4] == slip["period"][:4]]
        ytd = sum(self.gross(w, s) for s in mine if s["period"] < slip["period"])  # BUG-25: leaves out this month
        return {"id": slip["id"], "name": person["name"], "title": person["title"], "period": slip["period"],
                "paid": slip["paid"], "salary": person["salary"], "hourly": hourly, "base": base,
                "overtime_hours": slip["overtime_hours"], "overtime": overtime, "expenses": slip["expenses"],
                "gross": gross, "taxable": taxable, "tax": tax, "pension": pension,
                "net": money(gross - tax - pension), "ytd_gross": money(ytd)}  # fmt: skip

    def gross(self, w: dict, slip: dict) -> float:
        person = self.person(w, slip["user"])
        hourly = money(person["salary"] / data.HOURS_A_YEAR)
        return money(person["salary"] / 12 + slip["overtime_hours"] * hourly + slip["expenses"])

    def payslips(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        mine = [s for s in w["payslips"] if s["user"] == user["person"]["id"]]
        return {"payslips": [self.payslip_view(w, s) for s in sorted(mine, key=lambda s: s["period"], reverse=True)]}

    def payslip(self, sess: dict, sid: int) -> dict:
        w, user = self.signed_in(sess)
        slip = next((s for s in w["payslips"] if s["id"] == sid), None)  # BUG-26: anyone's payslip by its number
        if not slip:
            raise ApiError(404, "We couldn't find that payslip.")
        return self.payslip_view(w, slip)

    def payslip_csv(self, sess: dict, sid: int) -> bytes:
        p = self.payslip(sess, sid)
        rows = [("Base salary", p["base"]), (f"Overtime ({p['overtime_hours']:g} h)", p["overtime"]),
                ("Expenses", p["expenses"]), ("Gross pay", p["gross"]), ("Income tax", -p["tax"]),
                ("Pension", -p["pension"]), ("Net pay", p["net"])]  # fmt: skip
        lines = ["Item,Amount (EUR)"] + [f"{k},{v:,.2f}" for k, v in rows]  # BUG-24: 4,000.00 is not quoted
        return ("\n".join(lines) + "\n").encode()

    # approvals

    def queue(self, w: dict, user: dict) -> list[dict]:
        me = user["person"]["id"]
        team = {p["id"]: p["name"] for p in w["people"] if p["manager"] == me}
        team[me] = user["person"]["name"]  # BUG-35: a manager's own claims land in their queue
        items = []
        for uid, sheets in w["timesheets"].items():
            for week, s in sheets.items():
                if uid in team and uid != me and s["status"] == "submitted":
                    total = sum(sum(r) for r in s["hours"].values())
                    items.append({"kind": "timesheet", "id": f"{uid}:{week}", "who": team[uid], "date": week,
                                  "summary": f"Week of {week}: {total:g} hours"})  # fmt: skip
        for r in w["leave"]:
            if r["user"] in team and r["user"] != me and r["status"] == "pending":
                half = " (half day)" if r["half"] else ""
                days = f"{r['days']:g} day{'' if r['days'] == 1 else 's'}{half}"
                items.append({"kind": "leave", "id": str(r["id"]), "who": team[r["user"]], "date": r["start"],
                              "summary": f"{r['start']} to {r['end']}: {days}"})  # fmt: skip
        for e in w["expenses"]:
            if e["user"] in team and e["status"] == "pending":
                summary = f"{e['category']}: {e['description']} ({money_label(e['reimbursable'])})"
                items.append(
                    {
                        "kind": "expense",
                        "id": str(e["id"]),
                        "who": team[e["user"]],
                        "date": e["date"],
                        "summary": summary,
                    }
                )
        return sorted(items, key=lambda i: (i["date"], i["kind"]))

    def approvals(self, sess: dict) -> dict:
        w, user = self.signed_in(sess, manager=True)
        return {"items": self.queue(w, user)}

    def decide(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess, manager=True)
        action = body.get("action")
        if action not in ("approve", "reject"):
            raise ApiError(400, "Approve or reject.")
        reason = _text(body, "reason", 300)  # BUG-37: a rejection needs a reason
        picked = body.get("items")
        if not isinstance(picked, list) or not picked:
            raise ApiError(400, "Choose something to approve or reject.")
        open_items = {(i["kind"], i["id"]) for i in self.queue(w, user)}
        status = "approved" if action == "approve" else "rejected"
        done = 0
        for item in picked:
            if not isinstance(item, dict) or (item.get("kind"), str(item.get("id"))) not in open_items:
                continue
            kind, iid = item["kind"], str(item["id"])
            if kind == "timesheet":
                uid, week = iid.split(":")
                sheet = w["timesheets"][int(uid)][week]
                sheet.update(status=status, comment=reason if status == "rejected" else "")
            elif kind == "leave":
                r = next(r for r in w["leave"] if r["id"] == int(iid))
                r.update(status=status, reason=reason if status == "rejected" else "")
            else:
                e = next(e for e in w["expenses"] if e["id"] == int(iid))
                e.update(status=status, reason=reason if status == "rejected" else "")
            done += 1
        return {"items": self.queue(w, user), "done": done}

    # home

    def home(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        uid = user["person"]["id"]
        now = w["today"]
        week = self.week_view(w, uid, data.monday(dt.date.fromisoformat(now)))
        b = w["balances"][uid]
        taken = sum(r["days"] for r in w["leave"] if r["user"] == uid and r["status"] == "approved" and r["end"] < now)
        slips = self.payslips(sess)["payslips"]
        return {
            "name": user["person"]["name"].split()[0],
            "week": {"total": week["total"], "status": week["status"], "week": week["week"]},
            "leave_left": b["allowance"] + b["carried"] - taken,  # BUG-39: ignores booked and pending leave
            "claims": self.expense_summary(w, uid),
            "payslip": slips[0] if slips else None,
            "holidays": [h for h in w["holidays"] if h["date"] >= now],
            "approvals": len(self.queue(w, user)) if user["manager"] else None,
        }


def render(path: str, store: Store, sess: dict, status_page: str | None = None) -> bytes:
    name, title, _ = PAGES[path] if not status_page else (status_page, "Page not found", None)
    if status_page == "403":
        title = "Managers only"
    user = store.user(sess)
    if not user:
        nav = '<a href="/" data-nav="landing">Welcome</a><a href="/help" data-nav="help">Policies</a>'
        account = '<a href="/login" id="login-link">Log in</a>'
    else:
        links = [("/home", "home", "Home"), ("/timesheet", "timesheet", "Timesheet"), ("/leave", "leave", "Leave"),
                 ("/expenses", "expenses", "Expenses"), ("/payslips", "payslips", "Payslips"),
                 ("/team", "team", "Team"), ("/people", "people", "People")]  # fmt: skip
        nav = "".join(f'<a href="{h}" data-nav="{k}">{t}</a>' for h, k, t in links)
        if user["manager"]:
            count = len(store.queue(store.world(sess), user))
            badge = f'<span class="badge" id="nav-count">{count}</span>'
            nav += f'<a href="/approvals" data-nav="approvals">Approvals {badge}</a>'
        nav += '<a href="/help" data-nav="help">Policies</a>'
        first = html.escape(user["person"]["name"].split()[0])
        account = f'<a href="/profile" class="who">{first}</a>'
        account += '<button type="button" id="logout" class="link">Log out</button>'
    script = f'<script src="/static/{name}.js" defer></script>' if (STATIC_DIR / f"{name}.js").exists() else ""
    content = (PAGES_DIR / f"{name}.html").read_text()
    if name == "help":
        w = store.world(sess)
        days = "".join(
            f"<li>{html.escape(h['name'])}: {dt.date.fromisoformat(h['date']):%A %-d %B %Y}</li>" for h in w["holidays"]
        )
        rates = " · ".join(f"1 {c} = €{r:g}" for c, r in data.RATES.items() if c != "EUR")
        content = content.replace("{{holidays}}", days).replace("{{rates}}", rates)
    out = (PAGES_DIR / "_layout.html").read_text()
    values = {
        "title": html.escape(title),
        "page": name,
        "role": ("manager" if user["manager"] else "employee") if user else "",
        "nav": nav,
        "account": account,
        "content": content,
        "scripts": script,
    }
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out.encode()


def make_handler(store: Store | None = None):
    store = store or Store()
    static = {f.name: f for f in STATIC_DIR.iterdir() if f.is_file() and f.suffix in STATIC_TYPES}

    class Handler(BaseHTTPRequestHandler):
        server_version = "kestrel"

        def log_message(self, fmt, *args):
            pass

        def _session(self) -> tuple[str, dict, bool]:
            sid = None
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                sid = cookie["kw_sid"].value if "kw_sid" in cookie else None
            except CookieError:
                pass
            new_sid, sess = store.session(sid)
            return new_sid, sess, new_sid != sid

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            if self._new_sid:
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie", f"kw_sid={self._sid}; Path=/; HttpOnly; SameSite=Lax{secure}")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Bad request.") from None
            if length > MAX_BODY:
                raise ApiError(413, "Request too large.")
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                raise ApiError(400, "Send JSON.") from None
            if not isinstance(payload, dict):
                raise ApiError(400, "Send a JSON object.")
            return payload

        def do_HEAD(self):
            self._handle("GET")

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method: str):
            self._sid, self._new_sid = None, False
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            query = parse_qs(url.query)
            try:
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                if path == "/robots.txt":
                    return self._send(200, b"User-agent: *\nAllow: /\n", "text/plain")
                if path.startswith("/static/") and path[8:] in static:
                    f = static[path[8:]]
                    return self._send(200, f.read_bytes(), STATIC_TYPES[f.suffix])
                with store.lock:
                    self._sid, sess, self._new_sid = self._session()
                    if path.startswith("/api/"):
                        body = self._body() if method == "POST" else {}
                        result = self._api(sess, method, path, body, query)
                        if isinstance(result, bytes):
                            extra = {"Content-Disposition": 'attachment; filename="payslip.csv"'}
                            return self._send(200, result, "text/csv; charset=utf-8", extra)
                        return self._json(200, result)
                    if method != "GET":
                        return self._send(405, b"Method not allowed", "text/plain", {"Allow": "GET, HEAD"})
                    if path not in PAGES:
                        return self._send(404, render("/", store, sess, "404"), "text/html; charset=utf-8")
                    role = PAGES[path][2]
                    user = store.user(sess)
                    if role and not user:
                        location = "/login?next=" + quote(self.path, safe="")
                        return self._send(302, b"", "text/plain", {"Location": location})
                    if role == "manager" and not user["manager"]:
                        return self._send(403, render("/", store, sess, "403"), "text/html; charset=utf-8")
                    return self._send(200, render(path, store, sess), "text/html; charset=utf-8")
            except ApiError as err:
                return self._json(err.status, {"ok": False, "error": str(err)})
            except Exception:
                return self._json(500, {"ok": False, "error": "Internal Server Error"})

        def _api(self, sess: dict, method: str, path: str, body: dict, query: dict):
            if method == "GET":
                gets = {
                    "/api/me": lambda: store.me(sess),
                    "/api/home": lambda: store.home(sess),
                    "/api/people": lambda: store.people(sess, query),
                    "/api/profile": lambda: store.profile(sess),
                    "/api/timesheet": lambda: store.timesheet(sess, (query.get("week") or [""])[0]),
                    "/api/leave": lambda: store.leave(sess),
                    "/api/team": lambda: store.team(sess),
                    "/api/expenses": lambda: store.expenses(sess),
                    "/api/payslips": lambda: store.payslips(sess),
                    "/api/approvals": lambda: store.approvals(sess),
                }
                if path in gets:
                    return gets[path]()
                routes = (
                    (r"/api/payslips/(\d+)", lambda i: store.payslip(sess, int(i))),
                    (r"/api/payslips/(\d+)\.csv", lambda i: store.payslip_csv(sess, int(i))),
                )
            else:
                posts = {
                    "/api/login": lambda: store.login(sess, body),
                    "/api/logout": lambda: sess.update(user=None) or {"ok": True},
                    "/api/profile": lambda: store.save_profile(sess, body),
                    "/api/profile/emergency": lambda: store.save_emergency(sess, body),
                    "/api/leave": lambda: store.request_leave(sess, body),
                    "/api/expenses": lambda: store.claim(sess, body),
                    "/api/approvals": lambda: store.decide(sess, body),
                }
                if path in posts:
                    return posts[path]()
                routes = (
                    (r"/api/timesheet/([\d-]+)", lambda i: store.save_timesheet(sess, i, body)),
                    (r"/api/timesheet/([\d-]+)/submit", lambda i: store.submit_timesheet(sess, i)),
                    (r"/api/leave/(\d+)/cancel", lambda i: store.cancel_leave(sess, int(i))),
                )
            for pattern, run in routes:
                m = re.fullmatch(pattern, path)
                if m:
                    return run(m.group(1))
            raise ApiError(404, "Not found.")

    return Handler


def serve(env: dict[str, str] | None = None) -> None:
    env = dict(os.environ if env is None else env)
    port = int(env.get("PORT", "8084"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler())
    print(f"Kestrel Works listening on :{port}", flush=True)
    httpd.serve_forever()
