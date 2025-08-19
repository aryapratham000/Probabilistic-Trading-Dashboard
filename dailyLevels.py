from datetime import datetime, timedelta, time
from data import get_hist_bars
import pytz

# shared levels dict
levels = {
    "pdHigh": None,
    "pdLow": None,
    "pdClose": None,
    "pdOpen": None,
    "open": None,
    "High": None,
    "Low": None,
    "overnightHigh": None,
    "overnightLow": None,
    "vwap": None,
    "rollingHigh": None,
    "rollingLow": None,
}

rth_start = time(9, 30)
rth_end = time(16, 0)
overnight_start = time(18, 0)
overnight_end = time(9, 30)

def initialize_daily_levels(contract_id):
    # 1. Fetch past 3 days of 5-min bars
    bars = get_hist_bars(contract_id, lookback_min=5 * 24 * 60, unit=2, unit_number=5)
    if not bars:
        print("❌ Failed to initialize: no data.")
        return

    pd_rth = []
    today_rth = []
    overnight = []

    today = datetime.now(pytz.timezone("America/New_York")).date()  # e.g., July 18, 2025

    # Prior Day RTH: 9:30–16:00
    # Step 1: Group bars by date
    bars_by_date = {}
    for bar in bars:
        d = bar["t"].date()
        bars_by_date.setdefault(d, []).append(bar)

    prior_day = None
    for offset in range(1, 5):  # Check up to 4 days back
        check_date = today - timedelta(days=offset)
        session = [b for b in bars_by_date.get(check_date, []) if rth_start <= b["t"].time() <= rth_end]
        if session:
            prior_day = check_date
            pd_rth = session
            break

    bars_930 = sorted([b for b in bars if b["t"].time() == time(9, 30)], key=lambda b: b["t"])
    levels["pdOpen"] = bars_930[-2]["o"]
    levels["open"] = bars_930[-1]["o"]

    for bar in bars:
        date = bar["t"].date()
        bar_time = bar["t"].time()

        # Overnight: after 6pm yesterday or before 6am today
        if datetime.now(pytz.timezone("America/New_York")).time() >= datetime.strptime("18:00", "%H:%M").time():
            if date == today and bar_time >= datetime.strptime("18:00", "%H:%M").time():
                overnight.append(bar)
        else:
            if (date == today - timedelta(days=1) and bar_time >= datetime.strptime("18:00", "%H:%M").time()) or \
           (date == today and bar_time < datetime.strptime("06:00", "%H:%M").time()):
                overnight.append(bar)

        # Today RTH: 9:30–16:00
        if date == today and bar_time >= datetime.strptime("09:30", "%H:%M").time() and bar_time <= datetime.strptime("16:00", "%H:%M").time():
            today_rth.append(bar)

    # 3. Compute levels
    def high(bars): return max(bar["h"] for bar in bars) if bars else None
    def low(bars): return min(bar["l"] for bar in bars) if bars else None

    if pd_rth:
        levels["pdHigh"] = high(pd_rth)
        levels["pdLow"] = low(pd_rth)
        levels["pdClose"] = pd_rth[0]["c"]

    if overnight:
        levels["overnightHigh"] = high(overnight)
        levels["overnightLow"] = low(overnight)

    if today_rth:
        levels["High"] = high(today_rth)
        levels["Low"] = low(today_rth)

    if datetime.now(pytz.timezone("America/New_York")).time() >= datetime.strptime("18:00", "%H:%M").time():
        vwap_bars = overnight
    else:
        vwap_bars = overnight + today_rth
    
    if vwap_bars:
        # Compute VWAP
        total_pv = 0
        total_vol = 0
        for bar in vwap_bars:
            typical_price = (bar["o"] + bar["h"] + bar["l"] + bar["c"]) / 4
            volume = bar["v"]
            total_pv += typical_price * volume
            total_vol += volume
        levels["vwap"] = round(total_pv / total_vol, 2) if total_vol else None


    today_all = [b for b in bars if b["t"].date() == today]
    if today_all:
        levels["rollingHigh"] = high(today_all)
        levels["rollingLow"] = low(today_all)

    print("✅ Daily levels initialized:")
    for k, v in levels.items():
        print(f"{k}: {v}")
  
    return {
    "levels": levels,  # dict of actual interaction levels
    "vwap_pv": total_pv,
    "vwap_vol": total_vol
    }
    
    
    
def update_live_levels(bar, dailyLevels):

    bar_date = bar["t"].date()
    bar_time = bar["t"].time()
    now_date = datetime.now(pytz.timezone("America/New_York")).date() 
    
    typical_price = (bar["o"] + bar["h"] + bar["l"] + bar["c"]) / 4

    # Update High/Low/Open
    if rth_start <= bar_time <= rth_end:
        if levels["High"] is None or bar["h"] > levels["High"]:
            levels["High"] = bar["h"]
        if levels["Low"] is None or bar["l"] < levels["Low"]:
            levels["Low"] = bar["l"]
        if bar_time == rth_start:
            levels["pdOpen"] = levels["open"]
            levels["open"] = bar["o"]

    if bar_time >= overnight_start or bar_time < overnight_end:
        if bar_time == overnight_start:
            levels["overnightHigh"] = None
            levels["overnightLow"] = None
        if levels["overnightHigh"] is None or bar["h"] > levels["overnightHigh"]:
            levels["overnightHigh"] = bar["h"]
        if levels["overnightLow"] is None or bar["l"] < levels["overnightLow"]:
            levels["overnightLow"] = bar["l"]

    # Update Rolling High/Low (00:00 reset)
    if bar_date == now_date:
        if levels["rollingHigh"] is None or bar["h"] > levels["rollingHigh"]:
            levels["rollingHigh"] = bar["h"]
        if levels["rollingLow"] is None or bar["l"] < levels["rollingLow"]:
            levels["rollingLow"] = bar["l"]
            
    if bar_time == time(0, 0):
        levels["rollingHigh"] = None
        levels["rollingLow"] = None

    # Update VWAP
    if bar_time == datetime.strptime("18:00", "%H:%M").time():
        dailyLevels["vwap_pv"] = 0
        dailyLevels["vwap_vol"] = 0
        
    dailyLevels["vwap_pv"] += typical_price * bar["v"]
    dailyLevels["vwap_vol"] += bar["v"]

    levels["vwap"] = round(dailyLevels["vwap_pv"] / dailyLevels["vwap_vol"], 2) if dailyLevels["vwap_vol"] else None
    print(f"🔄 Updated Levels | High: {levels['High']} Low: {levels['Low']} Open: {levels['open']} VWAP: {levels['vwap']}")
