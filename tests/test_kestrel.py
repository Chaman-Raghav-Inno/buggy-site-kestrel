"""Kestrel's server-side planted bugs stay planted (BUGS.md) and nothing it serves gives them away."""

import datetime as dt
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from kestrel import data, server

T = server.today()
MONDAY = data.monday(T)


def day(n: int) -> str:
    return (T + dt.timedelta(days=n)).isoformat()


def weekday(after: int, wd: int) -> dt.date:
    return data.weekday_on_or_after(T + dt.timedelta(days=after), wd)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())

    def request(self, path: str, body=None) -> tuple[int, bytes, dict]:
        payload = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=payload, headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def get(self, path: str, **query):
        status, raw, _ = self.request(path + ("?" + urlencode(query) if query else ""))
        return status, json.loads(raw)

    def post(self, path: str, body: dict | None = None):
        status, raw, _ = self.request(path, body or {})
        return status, json.loads(raw)

    def login(self, who: str) -> int:
        return self.post("/api/login", {"email": f"{who}@kestrel.test", "password": data.PASSWORD})[0]

    def leave(self, start, end=None, half=False):
        body = {"start": str(start), "end": str(end or start), "half": half}
        return self.post("/api/leave", body)

    def claim(self, **fields):
        body = {"date": day(-2), "category": "Travel", "description": "Test", "currency": "EUR"} | fields
        status, result = self.post("/api/expenses", body)
        return status, (max(result["claims"], key=lambda c: c["id"]) if status == 200 else result)


@pytest.fixture
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(server.Store()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def maya(base_url):
    c = Client(base_url)
    assert c.login("maya") == 200
    return c


@pytest.fixture
def leo(base_url):
    c = Client(base_url)
    assert c.login("leo") == 200
    return c


def test_pages_and_access(base_url, maya):
    visitor = Client(base_url)
    for path in ("/", "/help", "/login"):
        assert visitor.request(path)[0] == 200, path
    status, _, headers = visitor.request("/leave")
    assert status == 302 and headers["Location"] == "/login?next=%2Fleave"
    assert visitor.request("/nope")[0] == 404 and visitor.request("/healthz")[1] == b"ok"
    assert visitor.post("/api/login", {"email": "maya@kestrel.test", "password": "x"})[0] == 401
    assert maya.request("/approvals")[0] == 403 and maya.post("/api/approvals", {"action": "approve"})[0] == 403


def test_answer_key_is_never_served_or_hinted(base_url):
    visitor = Client(base_url)
    for path in ("/BUGS.md", "/static/../BUGS.md", "/server.py", "/data.py"):
        assert visitor.request(path)[0] == 404, path
    for folder in (server.STATIC_DIR, server.PAGES_DIR):
        for f in folder.iterdir():
            assert not re.search(r"bug|planted", f.read_text(), re.I), f.name


def test_timesheets(maya):
    last = maya.get("/api/timesheet", week=str(MONDAY - dt.timedelta(weeks=1)))[1]
    assert last["total"] == 40 and last["overtime"] == 4  # BUG-03
    week = str(MONDAY)
    hours = {p: [0] * 7 for p in data.PROJECTS}
    hours["Apollo app"][0] = 25
    assert maya.post(f"/api/timesheet/{week}", {"hours": hours})[0] == 200  # BUG-05
    hours["Apollo app"][0] = 7.3
    assert maya.post(f"/api/timesheet/{week}", {"hours": hours})[0] == 400
    hours["Apollo app"][0] = 8
    maya.post(f"/api/timesheet/{week}", {"hours": hours})
    assert maya.post(f"/api/timesheet/{week}/submit")[1]["status"] == "submitted"
    status, sheet = maya.post(f"/api/timesheet/{week}", {"hours": hours | {"Internal": [9] * 7}})
    assert status == 200 and sheet["status"] == "submitted"  # BUG-04


def test_leave_rules(maya):
    leave = maya.get("/api/leave")[1]
    assert leave["balance"]["carried"] == 8 and leave["balance"]["available"] == 18  # BUG-13: 15
    holiday = dt.date.fromisoformat(leave["holidays"][0]["date"])
    week = data.monday(holiday)
    mine = maya.leave(week, week + dt.timedelta(days=4))[1]["requests"]
    assert next(r for r in mine if r["start"] == str(week))["days"] == 5  # BUG-08
    half = weekday(45, 2)
    maya.leave(half, half, half=True)
    assert next(r for r in maya.get("/api/leave")[1]["requests"] if r["start"] == str(half))["days"] == 1  # BUG-11
    pending = next(r for r in leave["requests"] if r["status"] == "pending")
    assert maya.leave(pending["start"], pending["end"])[0] == 200  # BUG-09
    status, after = maya.leave(day(70), day(66))
    assert status == 200 and any(r["days"] == 0 for r in after["requests"])  # BUG-14
    start = weekday(90, 0)
    status, after = maya.leave(start, start + dt.timedelta(days=41))
    assert status == 200 and after["balance"]["available"] < 0  # BUG-10
    assert maya.leave(day(-3))[0] == 400


def test_cancelled_leave_still_counts(maya):  # BUG-12
    leave = maya.get("/api/leave")[1]
    booked = next(r for r in leave["requests"] if r["status"] == "approved" and r["start"] > leave["today"])
    after = maya.post(f"/api/leave/{booked['id']}/cancel")[1]
    assert after["balance"]["available"] == leave["balance"]["available"]


def test_team_calendar_shows_rejected_leave(maya):  # BUG-28
    team = maya.get("/api/team")[1]
    tomas = next(p for p in team["people"] if p["name"] == "Tomás Ortega")
    assert [a["status"] for a in tomas["absences"]] == ["rejected"]


def test_expenses(maya):
    assert maya.get("/api/expenses")[1]["summary"]["pending"] == 215.0  # BUG-21: 180
    assert maya.claim(currency="GBP", amount=24)[0] == 200  # BUG-16: €28.08 with no receipt
    assert maya.claim(amount=26)[0] == 400
    assert maya.claim(category="Meals", amount=80, receipt="r.pdf")[1]["reimbursable"] == 80  # BUG-17
    assert maya.claim(category="Mileage", km=500)[1]["reimbursable"] == 225  # BUG-18: 165
    assert maya.claim(date=day(-120), amount=20)[0] == 200  # BUG-19
    assert maya.claim(date=day(1), amount=20)[0] == 400


def test_payslips(maya):
    slip = next(s for s in maya.get("/api/payslips")[1]["payslips"] if s["expenses"])
    assert slip["taxable"] == slip["gross"]  # BUG-22: expenses taxed
    assert slip["overtime"] == round(slip["overtime_hours"] * slip["hourly"], 2)  # BUG-23: should be 1.5 times
    status, raw, _ = maya.request(f"/api/payslips/{slip['id']}.csv")
    assert raw.decode().splitlines()[1] == "Base salary,4,000.00"  # BUG-24
    leo = maya.get("/api/payslips/4")[1]
    assert leo["name"] == "Leo Brandt"  # BUG-26
    assert maya.get("/api/payslips/999")[0] == 404


def test_ytd_leaves_out_the_month():  # BUG-25
    w = data.world(dt.date(2026, 11, 2))
    store = server.Store()
    first = next(s for s in w["payslips"] if s["user"] == 1 and s["period"] == "2026-08-01")
    assert store.payslip_view(w, first)["ytd_gross"] == 0


def test_people_and_profile(maya):
    assert maya.get("/api/people", q="Okafor")[1]["total"] == 0  # BUG-29
    assert maya.get("/api/people", q="maya")[1]["total"] == 1
    first = maya.get("/api/people", sort="start")[1]["people"][0]
    assert first["name"] != "Daniel Weiss"  # BUG-30
    saved = maya.post("/api/profile", {"phone_number": "+44 7700 900456", "iban": "GB82WEST12345698765432"})[1]
    assert saved["phone"] == "+44 20 7946 0001"  # BUG-33
    assert maya.post("/api/profile", {"iban": "GB82 WEST 1234 5698 7654 32"})[0] == 200
    assert maya.post("/api/profile", {"iban": "nope"})[0] == 400


def test_approvals(leo):
    items = leo.get("/api/approvals")[1]["items"]
    own = next(i for i in items if i["who"] == "Leo Brandt")  # BUG-35
    assert leo.post("/api/approvals", {"action": "approve", "items": [own]})[1]["done"] == 1
    sheet = next(i for i in items if i["kind"] == "timesheet")
    assert leo.post("/api/approvals", {"action": "reject", "reason": "", "items": [sheet]})[1]["done"] == 1  # BUG-37


def test_home_leave_ignores_bookings(maya):  # BUG-39
    assert maya.get("/api/home")[1]["leave_left"] == 21
    assert maya.get("/api/leave")[1]["balance"]["available"] == 18


def test_bad_requests(maya):
    assert maya.get("/api/timesheet", week="nope")[0] == 400
    assert maya.post("/api/expenses", {"category": "Travel"})[0] == 400
    assert maya.post("/api/leave/999/cancel")[0] == 404
