#!/usr/bin/env python3
"""
Monthly Profit and Loss Analysis: Income and Expenses
-----------------------------------------------------
Tools: Python, SQL, statistics, math, and matplotlib for the charts.

  1. SQL         schema.sql defines the categories (the options you choose from) and the
                 transactions table. queries.sql holds the queries that consolidate the data.
  2. Python      loads the entries, runs the queries, then applies statistics and maths:
                 mean, median, standard deviation, month-on-month rate of change,
                 savings rate and a least-squares trend line with a next-month forecast.
  3. Graphics    matplotlib draws income vs expenses, expense share by category and
                 the profit trend, and saves them as pnl_report.png.

Sections and options
    Income   : Salary, Business, Other income
    Expenses : Rent, Shopping, Snacks, Clothes
(change them in schema.sql; the menus below read them from the database)

Usage
    python analysis.py                    # built-in sample data
    python analysis.py --enter            # type your own entries: pick section, category, amount
    python analysis.py --csv my_data.csv  # columns: date,kind,category,amount
    python analysis.py --show             # also open the chart window
Install the chart library once with:  pip install matplotlib
"""
import argparse
import csv
import json
import math
import sqlite3
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ---- sample data: one value per month, per (section, category) --------------
SAMPLE = {
    ("income", "Salary"):       [30000] * 12,
    ("income", "Business"):     [8000, 3000, 12000, 15000, 2000, 14000, 20000, 16000, 1000, 25000, 22000, 30000],
    ("income", "Other income"): [0, 0, 2000, 0, 1000, 0, 3000, 0, 0, 5000, 2000, 0],
    ("expense", "Rent"):        [15000] * 12,
    ("expense", "Shopping"):    [8000, 9000, 7500, 8500, 9500, 8000, 10000, 9000, 11000, 9500, 12000, 13000],
    ("expense", "Snacks"):      [3000, 3200, 2800, 3500, 3000, 3400, 3600, 3300, 3800, 3500, 4000, 4200],
    ("expense", "Clothes"):     [2000, 6000, 1500, 2500, 7000, 2000, 3000, 8000, 10000, 3000, 5000, 9000],
}


def sample_rows(year):
    rows = []
    for (kind, category), values in SAMPLE.items():
        for month, amount in enumerate(values, start=1):
            if amount:
                rows.append((f"{year}-{month:02d}-15", kind, category, float(amount)))
    return rows


def csv_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((r["date"].strip(), r["kind"].strip().lower(), r["category"].strip(), float(r["amount"])))
    return rows


# ---- SQL helpers ------------------------------------------------------------
def load_queries(path):
    queries, name, buf = {}, None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(buf).strip()
            name, buf = line.split(":", 1)[1].strip(), []
        elif name:
            buf.append(line)
    if name:
        queries[name] = "\n".join(buf).strip()
    return queries


QUERIES = load_queries(BASE / "queries.sql")


def new_database():
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))
    return con


def add_rows(con, rows):
    con.executemany("INSERT INTO transactions (txn_date, kind, category, amount) VALUES (?, ?, ?, ?)", rows)


def get_categories(con):
    cats = {"income": [], "expense": []}
    for kind, name in con.execute(QUERIES["categories"]):
        cats[kind].append(name)
    return cats


# ---- typing your own entries ------------------------------------------------
def ask_choice(title, options):
    print(f"\n{title}")
    for i, option in enumerate(options, start=1):
        print(f"  {i}. {option}")
    while True:
        raw = input("Choose a number: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Please enter one of the numbers shown.")


def ask_number(prompt, low, high=None):
    while True:
        try:
            value = float(input(prompt).strip())
            if value >= low and (high is None or value <= high):
                return value
        except ValueError:
            pass
        print(f"Please enter a number from {low:g}" + (f" to {high:g}." if high else " upwards."))


def enter_rows(cats, year):
    rows = []
    while True:
        month = int(ask_number("\nMonth (1-12): ", 1, 12))
        section = ask_choice("Section:", ["Income", "Expenses"])
        kind = "income" if section == "Income" else "expense"
        category = ask_choice(f"{section} category:", cats[kind])
        amount = ask_number("Amount (Rs): ", 0)
        rows.append((f"{year}-{month:02d}-15", kind, category, amount))
        print(f"Added: {MONTHS[month - 1]} | {section} | {category} | Rs {amount:,.0f}")
        if input("Add another entry? (y/n): ").strip().lower() != "y":
            return rows


# ---- statistics and maths ---------------------------------------------------
def rate_of_change(values):
    """Month-on-month change in %, relative to the previous month's size."""
    rates = [None]
    for prev, curr in zip(values, values[1:]):
        rates.append((curr - prev) / abs(prev) * 100 if prev != 0 else 0.0)
    return rates


def linear_trend(values):
    """Least-squares line y = intercept + slope * month_number. Returns None for < 2 points."""
    n = len(values)
    if n < 2:
        return None
    xs = range(1, n + 1)
    sx, sy = math.fsum(xs), math.fsum(values)
    sxy = math.fsum(x * y for x, y in zip(xs, values))
    sxx = math.fsum(x * x for x in xs)
    denominator = n * sxx - sx * sx
    if math.isclose(denominator, 0):
        return None
    slope = (n * sxy - sx * sy) / denominator
    return slope, (sy - slope * sx) / n


def shares(rows):
    total = math.fsum(t for _, t in rows)
    return [{"category": c, "total": t, "share": t / total * 100 if total else 0.0} for c, t in rows]


def build_report(con):
    monthly = con.execute(QUERIES["monthly_profit_loss"]).fetchall()
    if not monthly:
        raise SystemExit("No entries to analyse.")
    running = dict(con.execute(QUERIES["running_total"]).fetchall())
    net = [row[3] for row in monthly]
    rates = rate_of_change(net)
    later = [r for r in rates if r is not None]
    trend = linear_trend(net)
    total_income = math.fsum(row[1] for row in monthly)
    total_expenses = math.fsum(row[2] for row in monthly)

    months = [
        {"month": m, "income": i, "expenses": e, "profit_loss": p, "rate_of_change": r, "running_total": running[m]}
        for (m, i, e, p), r in zip(monthly, rates)
    ]
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit_loss": total_income - total_expenses,
        "savings_rate": (total_income - total_expenses) / total_income * 100 if total_income else 0.0,
        "mean_monthly_profit": statistics.mean(net),
        "median_monthly_profit": statistics.median(net),
        "std_dev_monthly_profit": statistics.stdev(net) if len(net) > 1 else None,
        "average_rate_of_change": sum(later) / len(later) if later else 0.0,
        "trend_slope_per_month": trend[0] if trend else None,
        "forecast_next_month": trend[1] + trend[0] * (len(net) + 1) if trend else None,
        "best_month": max(months, key=lambda r: r["profit_loss"])["month"],
        "weakest_month": min(months, key=lambda r: r["profit_loss"])["month"],
        "expense_by_category": shares(con.execute(QUERIES["expense_by_category"]).fetchall()),
        "income_by_category": shares(con.execute(QUERIES["income_by_category"]).fetchall()),
        "months": months,
    }


# ---- output -----------------------------------------------------------------
def month_label(key):
    return MONTHS[int(key[5:7]) - 1]


def print_report(rep):
    print(f"\n{'Month':<7}{'Income':>12}{'Expenses':>12}{'Profit/Loss':>14}{'Change %':>11}")
    print("-" * 56)
    for m in rep["months"]:
        rate = "-" if m["rate_of_change"] is None else f"{m['rate_of_change']:.1f}"
        print(f"{month_label(m['month']):<7}{m['income']:>12,.0f}{m['expenses']:>12,.0f}{m['profit_loss']:>14,.0f}{rate:>11}")
    print("-" * 56)
    print(f"Total income     : Rs {rep['total_income']:,.0f}")
    print(f"Total expenses   : Rs {rep['total_expenses']:,.0f}")
    print(f"Net profit/loss  : Rs {rep['net_profit_loss']:,.0f}   (savings rate {rep['savings_rate']:.1f}%)")
    sd = rep["std_dev_monthly_profit"]
    print(f"Monthly profit   : mean {rep['mean_monthly_profit']:,.0f} | median {rep['median_monthly_profit']:,.0f} | std dev "
          + ("n/a" if sd is None else f"{sd:,.0f}"))
    print(f"Avg rate of change: {rep['average_rate_of_change']:.2f}%")
    if rep["forecast_next_month"] is not None:
        print(f"Trend            : {rep['trend_slope_per_month']:+,.0f} per month | next-month forecast Rs {rep['forecast_next_month']:,.0f}")
    print(f"Best month: {month_label(rep['best_month'])} | Weakest month: {month_label(rep['weakest_month'])}")
    print("\nExpenses by category:")
    for c in rep["expense_by_category"]:
        print(f"  {c['category']:<12}{c['total']:>12,.0f}  {c['share']:5.1f}%")
    print("Income by category:")
    for c in rep["income_by_category"]:
        print(f"  {c['category']:<12}{c['total']:>12,.0f}  {c['share']:5.1f}%")


def save_report(rep):
    (BASE / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    with open(BASE / "report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rep["months"][0].keys()))
        w.writeheader()
        w.writerows(rep["months"])


def draw_charts(rep, show=False):
    try:
        import matplotlib
        if not show:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Charts skipped. Install matplotlib with: pip install matplotlib")
        return
    INCOME, EXPENSE, NET, BG, PANEL, TEXT = "#f5a524", "#2dd4bf", "#6366f1", "#0e1015", "#151821", "#e8e6e1"
    labels = [month_label(m["month"]) for m in rep["months"]]
    income = [m["income"] for m in rep["months"]]
    expenses = [m["expenses"] for m in rep["months"]]
    net = [m["profit_loss"] for m in rep["months"]]
    x = list(range(len(labels)))

    fig = plt.figure(figsize=(13, 9), facecolor=BG)
    grid = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.25)
    top, left, right = fig.add_subplot(grid[0, :]), fig.add_subplot(grid[1, 0]), fig.add_subplot(grid[1, 1])
    for ax in (top, left, right):
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=TEXT)
        ax.title.set_color(TEXT)
        for spine in ax.spines.values():
            spine.set_color("#2a2f3a")

    top.bar([i - 0.2 for i in x], income, 0.4, color=INCOME, label="Income")
    top.bar([i + 0.2 for i in x], expenses, 0.4, color=EXPENSE, label="Expenses")
    top.plot(x, net, color=NET, marker="o", linewidth=2, label="Profit / loss")
    top.axhline(0, color="#4a5160", linewidth=1)
    top.set_xticks(x, labels)
    top.set_title("Income vs expenses by month (Rs)")
    top.legend(facecolor=PANEL, labelcolor=TEXT, edgecolor="#2a2f3a")

    cats = rep["expense_by_category"][::-1]
    left.barh([c["category"] for c in cats], [c["total"] for c in cats], color=EXPENSE)
    for i, c in enumerate(cats):
        left.text(c["total"], i, f"  {c['share']:.0f}%", va="center", color=TEXT)
    left.set_title("Where the money went (expenses by category)")

    right.plot(x, net, color=NET, marker="o", linewidth=2, label="Profit / loss")
    trend = linear_trend(net)
    if trend:
        slope, intercept = trend
        right.plot(x + [len(x)], [intercept + slope * (i + 1) for i in range(len(x) + 1)],
                   color=INCOME, linestyle="--", label="Trend line")
        right.scatter([len(x)], [rep["forecast_next_month"]], color=INCOME, marker="*", s=160, zorder=3, label="Forecast")
    right.axhline(0, color="#4a5160", linewidth=1)
    right.set_xticks(x + [len(x)], labels + ["Next"])
    right.set_title("Profit trend and next-month forecast")
    right.legend(facecolor=PANEL, labelcolor=TEXT, edgecolor="#2a2f3a")

    fig.savefig(BASE / "pnl_report.png", dpi=140, facecolor=BG, bbox_inches="tight")
    print("Saved pnl_report.png")
    if show:
        plt.show()


def main():
    ap = argparse.ArgumentParser(description="Monthly Profit and Loss Analysis")
    ap.add_argument("--csv", help="CSV with columns date,kind,category,amount")
    ap.add_argument("--enter", action="store_true", help="type your own income and expense entries")
    ap.add_argument("--year", type=int, default=2025, help="year used for entered / sample data")
    ap.add_argument("--show", action="store_true", help="open the chart window")
    args = ap.parse_args()

    con = new_database()
    if args.enter:
        rows = enter_rows(get_categories(con), args.year)
    elif args.csv:
        rows = csv_rows(args.csv)
    else:
        rows = sample_rows(args.year)
    try:
        add_rows(con, rows)
    except sqlite3.IntegrityError as err:
        raise SystemExit(f"Invalid entry: {err}. Use the categories listed in schema.sql.")

    report = build_report(con)
    print_report(report)
    save_report(report)
    print("\nSaved report.csv and report.json")
    draw_charts(report, args.show)


if __name__ == "__main__":
    main()
