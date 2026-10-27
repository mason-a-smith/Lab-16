"""Apply a publication-date provenance gate using only the standard library."""

# EDITABLE INPUTS: row numbers are provenance labels, not part of duplicate identity.
DECISION_DATE = "2026-03-31"
FACE_VALUE = "100"  # One-year zero-coupon bonds, same maturity and face value.
CREDIT_ORDER = ("AAA", "BBB", "CCC")  # Safest to riskiest.
TABLE = """Row,Ticker,Month measured,Published on,Price
1,AAA,2026-01,2026-02-10,101.0
2,AAA,2026-02,2026-03-10,104.0
3,AAA,2026-03,2026-04-10,109.0
4,AAA,2026-02,2026-03-25,103.0
5,BBB,2026-01,2026-02-10,98.0
6,BBB,2026-02,2026-03-10,97.0
7,BBB,2026-02,2026-03-10,97.0
8,BBB,2026-03,2026-04-10,92.0
9,CCC,2026-01,2026-02-10,110.0
10,CCC,2026-02,2026-04-05,112.0
11,,2026-02,2026-03-10,99.0
12,CCC,2026-02,2026-03-10,111.0
"""

import csv
from datetime import date
from decimal import Decimal
from io import StringIO


def read_inputs():
    rows = []
    for record in csv.DictReader(StringIO(TABLE.strip())):
        rows.append({
            "row": int(record["Row"]),
            "ticker": record["Ticker"].strip(),
            "month": date.fromisoformat(record["Month measured"].strip() + "-01"),
            "published": date.fromisoformat(record["Published on"].strip()),
            "price": Decimal(record["Price"].strip()),
        })
    return rows


def latest_publications(rows):
    """Keep the latest publication per ticker/month; first row wins a date tie."""
    latest = {}
    for row in rows:
        key = (row["ticker"], row["month"])
        if key not in latest or row["published"] > latest[key]["published"]:
            latest[key] = row
    return sorted(latest.values(), key=lambda row: (row["ticker"], row["month"]))


def report_rule(number, description, removed, remaining):
    numbers = ", ".join(str(row["row"]) for row in removed) or "none"
    print(f"Rule {number} ({description}): removed {len(removed)}; "
          f"row numbers: {numbers}; remaining {len(remaining)}")


def print_signals(label, panel, tickers):
    print(f"\n{label}")
    for ticker in tickers:
        observations = sorted((r for r in panel if r["ticker"] == ticker),
                              key=lambda r: r["month"])
        if len(observations) < 2:
            print(f"{ticker}: unavailable (need two months)")
            continue
        previous, latest = observations[-2:]
        month_gap = ((latest["month"].year - previous["month"].year) * 12
                     + latest["month"].month - previous["month"].month)
        if month_gap != 1 or previous["price"] == 0:
            print(f"{ticker}: unavailable (missing previous month or zero prior price)")
            continue
        change = (latest["price"] / previous["price"] - 1) * 100
        print(f"{ticker}: {latest['month']:%Y-%m} signal {change:+.2f}% "
              f"(from {previous['month']:%Y-%m}; "
              f"rows {previous['row']} -> {latest['row']})")


def print_sanity_checks(panel):
    """Flag economic inconsistencies without changing the provenance panel."""
    print("\nYield / sanity check (as-of panel)")
    print("Yield = (face value / price - 1) * 100; one-year zero-coupon bonds")
    print("Row  Fund  Month    Price     Yield     Breaks")
    rank = {ticker: i for i, ticker in enumerate(CREDIT_ORDER)}
    for row in panel:
        issues = []
        price = row["price"]
        if price <= 0:
            yield_text = "N/A"
            issues.append("nonpositive price")
        else:
            bond_yield = (Decimal(FACE_VALUE) / price - 1) * 100
            yield_text = f"{bond_yield:+.2f}%"
            if bond_yield < 0:
                issues.append("negative yield")
        if row["ticker"] in rank:
            safer = sorted(
                (other for other in panel
                 if other["month"] == row["month"]
                 and other["ticker"] in rank
                 and rank[other["ticker"]] < rank[row["ticker"]]
                 and price >= other["price"]),
                key=lambda other: rank[other["ticker"]], reverse=True)
            above = [other["ticker"] for other in safer if price > other["price"]]
            equal = [other["ticker"] for other in safer if price == other["price"]]
            if above:
                issues.append("priced above " + " and ".join(above))
            if equal:
                issues.append("priced equal to " + " and ".join(equal))
        print(f"{row['row']:>3}  {row['ticker']:<4}  {row['month']:%Y-%m}  "
              f"{price:>6}  {yield_text:>8}  {'; '.join(issues) or 'nothing'}")
    print("On time is not the same as true: a provenance gate needs a sanity "
          "gate behind it.")


def main():
    decision = date.fromisoformat(DECISION_DATE)
    original = read_inputs()
    active = original[:]
    print(f"Decision date: {decision}\nRow funnel: starting with {len(active)} rows")

    removed = [r for r in active if not r["ticker"]]
    active = [r for r in active if r["ticker"]]
    report_rule(1, "quarantine missing ticker", removed, active)

    seen, retained, removed = set(), [], []
    for row in active:
        key = (row["ticker"], row["month"], row["published"], row["price"])
        if key in seen:
            removed.append(row)
        else:
            seen.add(key)
            retained.append(row)
    active = retained
    report_rule(2, "exact duplicate excluding row number", removed, active)

    removed = [r for r in active if r["published"] > decision]
    active = [r for r in active if r["published"] <= decision]
    report_rule(3, "published after decision date", removed, active)

    panel = latest_publications(active)
    retained_ids = {r["row"] for r in panel}
    removed = [r for r in active if r["row"] not in retained_ids]
    report_rule(4, "superseded publication", removed, panel)

    print("\nAs-of panel")
    print("Row  Ticker  Month    Published   Price")
    for row in panel:
        print(f"{row['row']:>3}  {row['ticker']:<6}  {row['month']:%Y-%m}  "
              f"{row['published']}  {row['price']}")

    tickers = sorted({r["ticker"] for r in original if r["ticker"]})
    print_signals("As-of signals", panel, tickers)
    # Same ticker/month revision selection, but deliberately omit the date gate.
    # Missing tickers cannot define a signal; exact duplicates do not change it.
    naive = latest_publications([r for r in original if r["ticker"]])
    print_signals("Naive signals (latest publications, ignoring decision date)",
                  naive, tickers)
    print("\nThese four rules check provenance only; they do not validate "
          "yields or credit-price ordering.")
    print_sanity_checks(panel)


if __name__ == "__main__":
    main()
