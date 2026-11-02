"""Kestrel Works' demo world: people, timesheets, leave, expenses and payslips, dated from today.

Every visitor gets a fresh copy (see server.Store), so scans never disturb each other.
"""

import datetime as dt
import hashlib
import unicodedata

PASSWORD = "Kestrel@2026"
SALT = b"kestrel-demo-salt"

ALLOWANCE = 25
CARRY_CAP = 5
WEEK_HOURS = 40
HOURS_A_YEAR = 2080
OVERTIME_RATE = 1.5
TAX_RATE = 0.20
PENSION_RATE = 0.05
MEAL_CAP = 50.0
RECEIPT_OVER = 25.0
MILEAGE = ((10_000, 0.45), (None, 0.25))  # first 10,000 km a year, then the rest
CLAIM_DAYS = 90
RATES = {"EUR": 1.0, "USD": 0.92, "GBP": 1.17, "JPY": 0.0061}
PROJECTS = ["Apollo app", "Internal", "Training"]
CATEGORIES = ["Travel", "Meals", "Hotel", "Mileage", "Other"]

# fmt: off
PEOPLE = [
    # id, name, title, department, start date (y, m, d), salary, manager id
    (1, "Maya Okafor", "Product Designer", "Design", (2021, 3, 15), 48_000, 2),
    (2, "Leo Brandt", "Engineering Manager", "Engineering", (2017, 9, 4), 72_000, None),
    (3, "Ravi Patel", "Backend Engineer", "Engineering", (2019, 11, 18), 58_000, 2),
    (4, "Sofia Lindgren", "Frontend Engineer", "Engineering", (2022, 1, 10), 54_000, 2),
    (5, "Tomás Ortega", "QA Engineer", "Engineering", (2020, 6, 1), 50_000, 2),
    (6, "Hana Kim", "Data Analyst", "Engineering", (2023, 4, 24), 52_000, 2),
    (7, "Amara Nwosu", "People Partner", "People", (2018, 2, 12), 56_000, None),
    (8, "Ben Carter", "Account Executive", "Sales", (2021, 8, 30), 50_000, None),
    (9, "Chloé Dubois", "Marketing Lead", "Marketing", (2016, 5, 9), 64_000, None),
    (10, "Daniel Weiss", "Finance Controller", "Finance", (2015, 10, 1), 70_000, None),
    (11, "Elif Yılmaz", "Support Specialist", "Support", (2024, 2, 5), 38_000, None),
    (12, "Felix Brown", "DevOps Engineer", "Engineering", (2020, 12, 7), 60_000, None),
    (13, "Grace Ho", "UX Researcher", "Design", (2019, 4, 1), 52_000, None),
    (14, "Hugo Martins", "Sales Manager", "Sales", (2018, 7, 23), 66_000, None),
    (15, "Isla Murray", "Office Manager", "Operations", (2022, 9, 12), 40_000, None),
    (16, "Jonas Berg", "Mobile Engineer", "Engineering", (2023, 1, 16), 56_000, None),
    (17, "Kofi Mensah", "Recruiter", "People", (2021, 11, 1), 44_000, None),
    (18, "Lucía Fernández", "Content Designer", "Design", (2020, 3, 2), 47_000, None),
    (19, "Mei Lin", "Payroll Specialist", "Finance", (2017, 1, 9), 49_000, None),
    (20, "Nikolai Petrov", "Security Engineer", "Engineering", (2019, 8, 19), 68_000, None),
    (21, "Olivia Grant", "Customer Success", "Support", (2024, 6, 3), 41_000, None),
    (22, "Paulo Souza", "Data Engineer", "Engineering", (2021, 5, 17), 59_000, None),
    (23, "Quinn Taylor", "Legal Counsel", "Legal", (2016, 11, 28), 78_000, None),
    (24, "Zoë Martin", "Brand Designer", "Marketing", (2022, 10, 3), 46_000, None),
]
# fmt: on


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 20_000).hex()


DEMO_HASH = password_hash(PASSWORD, SALT)


def ascii_name(name: str) -> str:
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()


def monday(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def weekday_on_or_after(day: dt.date, weekday: int | None = None) -> dt.date:
    """The first weekday (or the given weekday, 0 = Monday) on or after day."""
    while day.weekday() >= 5 if weekday is None else day.weekday() != weekday:
        day += dt.timedelta(days=1)
    return day


def month_start(day: dt.date, back: int) -> dt.date:
    y, m = divmod(day.year * 12 + day.month - 1 - back, 12)
    return dt.date(y, m + 1, 1)


def world(today: dt.date) -> dict:
    """A fresh copy of everything one visitor can see and change."""

    def d(days: int) -> str:
        return (today + dt.timedelta(days=days)).isoformat()

    this_week = monday(today)

    def week(n: int) -> str:
        return (this_week + dt.timedelta(weeks=n)).isoformat()

    people = [
        {"id": i, "name": n, "title": t, "department": dep, "start": dt.date(*s).isoformat(), "salary": sal,
         "manager": mgr, "email": ascii_name(n.split()[0]) + "@kestrel.test",
         "phone": f"+44 20 7946 {i:04d}", "iban": "", "emergency": {"name": "", "phone": ""}}
        for i, n, t, dep, s, sal, mgr in PEOPLE
    ]  # fmt: skip
    people[0] |= {
        "iban": "GB82 WEST 1234 5698 7654 32",
        "emergency": {"name": "Tunde Okafor", "phone": "+44 7700 900123"},
    }

    holidays = []
    founders = weekday_on_or_after(today + dt.timedelta(days=10))
    holidays.append({"date": founders.isoformat(), "name": "Founders' Day"})
    autumn = weekday_on_or_after(today + dt.timedelta(days=38))
    holidays.append({"date": autumn.isoformat(), "name": "Company wellbeing day"})

    def hours(*rows):
        return {p: list(r) for p, r in zip(PROJECTS, rows, strict=False)}

    zero = [0] * 7
    timesheets = {
        1: {
            week(0): {"hours": hours([8, 7.5, 0, 0, 0, 0, 0], zero, zero), "status": "draft", "comment": ""},
            week(-1): {"hours": hours([10, 10, 5, 7, 6, 0, 0], [0, 0, 1, 1, 0, 0, 0], zero), "status": "approved",
                       "comment": ""},
            week(-2): {"hours": hours([8, 8, 8, 8, 0, 0, 0], zero, [0, 0, 0, 0, 8, 0, 0]), "status": "rejected",
                       "comment": "Friday was at the client, not Training: move it to Apollo app."},
            week(-3): {"hours": hours([8, 9, 9, 8, 8, 0, 0], zero, zero), "status": "approved", "comment": ""},
        },
        3: {week(-1): {"hours": hours([8, 8, 8, 8, 8, 0, 0], zero, zero), "status": "submitted", "comment": ""}},
        4: {week(-1): {"hours": hours([9, 9, 9, 9, 8, 0, 0], zero, zero), "status": "submitted", "comment": ""}},
    }  # fmt: skip

    def leave(rid, user, start, end, days, status, kind="Holiday", half=False, reason=""):
        return {"id": rid, "user": user, "start": start, "end": end, "days": days, "status": status, "kind": kind,
                "half": half, "note": "", "reason": reason, "created": d(-30)}  # fmt: skip

    past1 = weekday_on_or_after(today - dt.timedelta(days=95), 0)
    past2 = weekday_on_or_after(today - dt.timedelta(days=55), 0)
    booked = weekday_on_or_after(today + dt.timedelta(days=15), 0)
    pending = weekday_on_or_after(today + dt.timedelta(days=24), 4)
    ravi = weekday_on_or_after(today + dt.timedelta(days=3), 0)
    hana = weekday_on_or_after(today + dt.timedelta(days=7), 1)
    tomas = weekday_on_or_after(today + dt.timedelta(days=2), 2)

    def iso(day: dt.date, plus: int = 0) -> str:
        return (day + dt.timedelta(days=plus)).isoformat()

    leaves = [
        leave(1, 1, iso(past1), iso(past1, 4), 5, "approved"),
        leave(2, 1, iso(past2), iso(past2, 8), 7, "approved"),
        leave(3, 1, iso(booked), iso(booked, 1), 2, "approved"),
        leave(4, 1, iso(pending), iso(pending), 1, "pending"),
        leave(5, 3, iso(ravi), iso(ravi, 4), 5, "approved"),
        leave(6, 6, iso(hana), iso(hana, 2), 3, "pending"),
        leave(7, 5, iso(tomas), iso(tomas, 1), 2, "rejected", reason="Release week: please pick other dates."),
    ]

    def claim(cid, user, days_ago, category, description, currency, amount, status, **extra):
        eur = round(amount * RATES[currency], 2)
        base = {"id": cid, "user": user, "date": d(-days_ago), "category": category, "description": description,
                "currency": currency, "amount": amount, "km": 0, "eur": eur, "reimbursable": eur,
                "receipt": "receipt.pdf" if eur > RECEIPT_OVER else "", "status": status, "reason": "",
                "submitted": d(-days_ago + 1)}  # fmt: skip
        return base | extra

    expenses = [
        claim(1, 1, 50, "Travel", "Train to the Leeds client workshop", "EUR", 42.50, "paid"),
        claim(2, 1, 6, "Hotel", "Hotel in Leeds, one night", "EUR", 180.00, "pending"),
        claim(3, 1, 12, "Travel", "Taxi from the airport", "EUR", 35.00, "rejected", receipt="",
              reason="No receipt attached."),
        claim(4, 3, 4, "Travel", "Train to Bristol", "EUR", 64.20, "pending"),
        claim(5, 2, 3, "Meals", "Client dinner with Northwind", "EUR", 64.00, "pending"),
    ]  # fmt: skip

    payslips = []
    pid = 1
    for user, ot, claims in ((1, (2, 4, 0), (0, 42.50, 0)), (2, (0, 0, 0), (0, 0, 0))):
        for i, back in enumerate((3, 2, 1)):
            start = month_start(today, back)
            payslips.append({"id": pid, "user": user, "period": start.isoformat(), "overtime_hours": ot[i],
                             "expenses": claims[i], "paid": start.replace(day=25).isoformat()})  # fmt: skip
            pid += 1

    login = {"salt": SALT.hex(), "hash": DEMO_HASH}
    return {
        "today": today.isoformat(),
        "people": people,
        "users": [
            {"id": 1, "person": 1, "email": "maya@kestrel.test", "manager": False} | login,
            {"id": 2, "person": 2, "email": "leo@kestrel.test", "manager": True} | login,
        ],
        "balances": {1: {"allowance": ALLOWANCE, "carried": 8, "mileage_km": 9_800}, 2: {"allowance": ALLOWANCE,
                     "carried": 2, "mileage_km": 1_200}},
        "holidays": holidays,
        "timesheets": timesheets,
        "leave": leaves,
        "expenses": expenses,
        "payslips": payslips,
        "next_id": 100,
    }  # fmt: skip
