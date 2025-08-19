#data.py

import requests
from auth import get_headers
from config import PROJECTX_BASE_URL
from datetime import datetime, timedelta, timezone
import pytz
import asyncio
import json
from signalrcore.hub_connection_builder import HubConnectionBuilder
import auth
from collections import defaultdict


def get_hist_bars(contract_id, lookback_min=5555, live=False, unit=2, unit_number=1, limit=5000, include_partial=False):
    url = f"{PROJECTX_BASE_URL}/api/History/retrieveBars"

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=lookback_min)

    payload = {
        "contractId": contract_id,
        "live": live,
        "startTime": start_time.isoformat(),
        "endTime": end_time.isoformat(),
        "unit": unit,           
        "unitNumber": unit_number,        
        "limit": limit,
        "includePartialBar": include_partial
    }

    try:
        response = requests.post(url, json=payload, headers=get_headers())
        response.raise_for_status()
        data = response.json()

        bars = data.get("bars", [])
        if not bars:
            print("❌ No bars returned")
            return None
        
        # Convert timestamps to New York time
        ny_tz = pytz.timezone("America/New_York")
        for bar in bars:
            utc_dt = datetime.fromisoformat(bar["t"])
            ny_dt = utc_dt.astimezone(ny_tz)
            bar["t"] = ny_dt  # Keep as datetime object
        
        return bars

    except Exception as e:
        print("❌ Error fetching bar:", e)
        return None

async def latest_bar(contract_id, unit = 2, unit_number = 1, live = False):
    while True:
        await asyncio.sleep(60 - datetime.now(pytz.timezone("America/New_York")).second)

        bars = get_hist_bars(
            contract_id=contract_id,
            unit=unit,             # unit=2 = minute bars
            unit_number= unit_number,      # 1-minute bars
            limit=1,            # Just the latest bar
            live= live           
        )

        if bars:
            yield bars[0]  # stream it to caller




def aggregate_to_4h(bars):
    grouped = defaultdict(list)

    for bar in bars:
        dt = bar["t"]
        # Snap backward to nearest 4-hour block starting at 2:00
        anchor_hour = ((dt.hour - 2) // 4) * 4 + 2
        if anchor_hour < 0:
            anchor_hour += 24
            anchor_day = dt.date() - timedelta(days=1)
        else:
            anchor_day = dt.date()

        anchor = dt.replace(
            year=anchor_day.year,
            month=anchor_day.month,
            day=anchor_day.day,
            hour=anchor_hour,
            minute=0,
            second=0,
            microsecond=0
        )

        grouped[anchor].append(bar)

    h4bars = []
    for anchor in sorted(grouped.keys(), reverse=True):
        bars = grouped[anchor]
        bars.sort(key=lambda b: b["t"])
        if not bars:
            continue

        h4bars.append({
            "t": anchor,
            "o": bars[0]["o"],
            "h": max(b["h"] for b in bars),
            "l": min(b["l"] for b in bars),
            "c": bars[-1]["c"],
            "v": sum(b["v"] for b in bars)
        })

    return h4bars
