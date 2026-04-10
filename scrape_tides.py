#!/usr/bin/env python3
"""
scrape_tides.py – scrape Naha, Okinawa tide data from tidetime.org
and write the next ~3 weeks into data/tides.json

Usage:
    python3 scrape_tides.py

Requirements:
    pip3 install requests beautifulsoup4
"""

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip3 install requests beautifulsoup4")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOCATION = "Naha, Okinawa, Japan"
TIMEZONE = "JST"
BASE = "https://www.tidetime.org/asia/japan/naha-okinawa-japan-calendar"
WEEKS_AHEAD = 3

# URL suffix per month — April uses the bare base URL; others use "-mon"
MONTH_SLUGS = {
    1: "-jan", 2: "-feb", 3: "-mar",
    4: "",      # base URL (no suffix)
    5: "-may",  6: "-jun", 7: "-jul",
    8: "-aug",  9: "-sep", 10: "-oct",
    11: "-nov", 12: "-dec",
}

MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

# Table column index → tide type (col 0 = Day label)
TIDE_COLS = {1: "H", 2: "L", 3: "H", 4: "L", 5: "H"}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; tide-scraper/1.0)"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def month_url(year: int, month: int) -> str:
    return f"{BASE}{MONTH_SLUGS[month]}.htm"


def parse_time(text: str) -> str | None:
    """Extract '6:49 AM' from '6:49 AM JST 1.89 m'."""
    m = re.search(r'\d{1,2}:\d{2}\s+(?:AM|PM)', text)
    return m.group() if m else None


def parse_height(text: str) -> float | None:
    """Extract 1.89 from '6:49 AM JST 1.89 m', handling −0.13."""
    m = re.search(r'([−\-]?\d+\.\d+)\s*m', text)
    return float(m.group(1).replace('−', '-')) if m else None


def fetch_month(year: int, month: int) -> list[dict]:
    url = month_url(year, month)
    print(f"  Fetching {url}", file=sys.stderr)
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        print(f"  No table found at {url}", file=sys.stderr)
        return []

    days = []
    for row in table.find_all("tr")[1:]:   # skip header row
        cells = row.find_all("td")
        if not cells:
            continue

        day_raw = cells[0].get_text(strip=True)
        m = re.match(r'(\w{3})\s+(\d{1,2})', day_raw)
        if not m:
            continue
        weekday, day_num = m.group(1), int(m.group(2))

        try:
            d = date(year, month, day_num)
        except ValueError:
            continue

        # Tides from fixed H/L columns
        tides = []
        for col_idx, tide_type in TIDE_COLS.items():
            if col_idx >= len(cells):
                break
            cell = cells[col_idx].get_text(strip=True)
            t = parse_time(cell)
            h = parse_height(cell)
            if t and h is not None:
                tides.append({"type": tide_type, "time": t, "height_m": h})

        # Moon phase (col 6)
        moon_phase = None
        if len(cells) > 6:
            phase = cells[6].get_text(strip=True)
            if phase and phase != "—":
                moon_phase = phase or None

        # Sun/moon times (cols 7–10)
        def get_time(idx):
            if idx < len(cells):
                return parse_time(cells[idx].get_text(strip=True))
            return None

        days.append({
            "date": d.isoformat(),
            "label": f"{weekday} {day_num:02d} {MONTH_ABBR[month]}",
            "tides": tides,
            "moon_phase": moon_phase,
            "sunrise": get_time(7),
            "sunset":  get_time(8),
            "moonrise": get_time(9),
            "moonset":  get_time(10),
        })

    print(f"  Parsed {len(days)} days", file=sys.stderr)
    return days


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    today = date.today()
    end_date = today + timedelta(weeks=WEEKS_AHEAD)
    print(f"Scraping {today} → {end_date} ({WEEKS_AHEAD} weeks ahead)", file=sys.stderr)

    # Which year/month pairs span the window?
    months_needed: set[tuple[int, int]] = set()
    cursor = today
    while cursor <= end_date:
        months_needed.add((cursor.year, cursor.month))
        cursor += timedelta(days=28)
    months_needed.add((end_date.year, end_date.month))

    all_days: list[dict] = []
    for year, month in sorted(months_needed):
        if month not in MONTH_SLUGS:
            print(f"  Skipping {year}-{month:02d} (no URL mapping)", file=sys.stderr)
            continue
        all_days.extend(fetch_month(year, month))

    # Filter to the window
    filtered = [
        d for d in all_days
        if today.isoformat() <= d["date"] <= end_date.isoformat()
    ]

    output = {
        "location": LOCATION,
        "timezone": TIMEZONE,
        "generated": today.isoformat(),
        "source": f"{BASE}.htm",
        "days": filtered,
    }

    out_path = Path(__file__).parent / "data" / "tides.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(filtered)} days → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
