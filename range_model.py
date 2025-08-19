import pandas as pd
import numpy as np
from candleClassification import classify_markov
import auth
import statsmodels.api as sm

def _pattern_series_from_markov(df_ohlc: pd.DataFrame) -> pd.Series:
    idx = df_ohlc.index
    pat = pd.Series(index=idx, dtype="object")
    for i in range(1, len(df_ohlc)):
        curr = {
            "o": df_ohlc["open"].iloc[i],
            "h": df_ohlc["high"].iloc[i],
            "l": df_ohlc["low"].iloc[i],
            "c": df_ohlc["close"].iloc[i],
        }
        prev = {
            "h": df_ohlc["high"].iloc[i-1],
            "l": df_ohlc["low"].iloc[i-1],
            "o": df_ohlc["open"].iloc[i-1],
            "c": df_ohlc["close"].iloc[i-1],
        }
        pat.iloc[i] = classify_markov(curr, prev)
    pat.iloc[0] = None  # first row has no prior bar
    return pat

def make_features_1h(m1bars, h1bars, model_feature_names):
    # ---- 1) H1 frame (ascending) ----
    df1h = pd.DataFrame(h1bars).rename(
        columns={"t":"datetime","o":"open","h":"high","l":"low","c":"close","v":"volume"}
    ).sort_values("datetime").set_index("datetime")
    if df1h.empty:
        raise ValueError("make_features_1h: h1bars is empty")

    # ---- 2) Core features (training-consistent) ----
    df1h["range"] = df1h["high"] - df1h["low"]
    df1h["side"]  = (df1h["close"] >= df1h["open"]).astype(int)
    df1h["dayofweek"] = df1h.index.dayofweek
    df1h["session"]   = df1h.index.hour  # you used hour as session

    # ---- 4) Strong candle (shifted) ----
    df1h["is_strong_candle"] = ((df1h["close"] - df1h["open"]).abs() > 0.7*df1h["range"]).astype(int).shift(1)

    # ---- 5) Lags: range/side m1..m5 ----
    for k in range(1, 6):
        df1h[f"range_m{k}"] = df1h["range"].shift(k)
        df1h[f"side_m{k}"]  = df1h["side"].shift(k)

    # ---- 6) Patterns via your classify_markov + dummies + lagged dummies ----
    df1h["pattern"] = _pattern_series_from_markov(df1h[["open","high","low","close"]])
    pat_dum = pd.get_dummies(df1h["pattern"], prefix="pat", dtype=float, drop_first=True)
    df1h = df1h.join(pat_dum)

    base_pat_cols = [c for c in df1h.columns if c.startswith("pat_") and "_m" not in c]
    for k in (1, 2, 3):
        for col in base_pat_cols:
            df1h[f"{col}_m{k}"] = df1h[col].shift(k)

    # ---- 7) Session & DOW one-hots (drop_first=True) ----
    sess_dum = pd.get_dummies(df1h["session"], prefix="sess", dtype=float, drop_first=True)
    dow_dum  = pd.get_dummies(df1h["dayofweek"], prefix="dow", dtype=float, drop_first=True)
    df1h = df1h.join([sess_dum, dow_dum])

    # ---- NEW: Ensure all expected dummy columns exist ----
    for col in model_feature_names:
        if col not in df1h.columns:
            df1h[col] = 0.0
            
    # ---- 8) range_5min from first 5 minutes of current hour ----
    df1m = pd.DataFrame(m1bars).rename(
        columns={"t":"datetime","o":"open","h":"high","l":"low","c":"close","v":"volume"}
    ).sort_values("datetime").set_index("datetime")
    if df1m.empty:
        raise ValueError("make_features_1h: m1bars is empty")

    hour_start = df1h.index[-1]
    first5 = df1m.loc[(df1m.index >= hour_start) & (df1m.index < hour_start + pd.Timedelta(minutes=5))]
    if first5.empty:
        raise ValueError("make_features_1h: missing first 5 minutes for current hour")
    df1h.loc[hour_start, "range_5min"] = first5["high"].max() - first5["low"].min()

    # ---- 9) Extract the single, ordered feature row (strict) ----
    if hour_start not in df1h.index:
        raise ValueError("make_features_1h: hour_start row not found in h1bars index")
    feat_row = df1h.loc[[hour_start], :]

    missing = [c for c in model_feature_names if c not in feat_row.columns]
    if missing:
        raise ValueError(f"make_features_1h: missing required features: {missing}")

    X_one = feat_row[model_feature_names].copy()

    if X_one.isna().any().any():
        na_cols = X_one.columns[X_one.isna().any()].tolist()
        raise ValueError(f"make_features_1h: NaNs present in feature row: {na_cols}")

    return X_one












def make_features_4h(m1bars, h4bars, model_feature_names):
    # ---- 1) H4 frame (ascending) ----
    df4h = pd.DataFrame(h4bars).rename(
        columns={"t": "datetime", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    ).sort_values("datetime").set_index("datetime")
    if df4h.empty:
        raise ValueError("make_features_4h: h4bars is empty")

    # ---- 2) Core features (training-consistent) ----
    df4h["range"] = df4h["high"] - df4h["low"]
    df4h["side"] = (df4h["close"] >= df4h["open"]).astype(int)
    df4h["dayofweek"] = df4h.index.dayofweek
    df4h["session"] = df4h.index.hour  # used hour as session

    # ---- 4) Strong candle (shifted) ----
    df4h["is_strong_candle"] = ((df4h["close"] - df4h["open"]).abs() > 0.7 * df4h["range"]).astype(int).shift(1)

    # ---- 5) Lags: range/side m1..m5 ----
    for k in range(1, 6):
        df4h[f"range_m{k}"] = df4h["range"].shift(k)
        df4h[f"side_m{k}"] = df4h["side"].shift(k)

    # ---- 6) Patterns via classify_markov + dummies + lagged dummies ----
    df4h["pattern"] = _pattern_series_from_markov(df4h[["open", "high", "low", "close"]])
    pat_dum = pd.get_dummies(df4h["pattern"], prefix="pat", dtype=float, drop_first=True)
    df4h = df4h.join(pat_dum)

    base_pat_cols = [c for c in df4h.columns if c.startswith("pat_") and "_m" not in c]
    for k in (1, 2, 3):
        for col in base_pat_cols:
            df4h[f"{col}_m{k}"] = df4h[col].shift(k)

    # ---- 7) Session & DOW one-hots ----
    sess_dum = pd.get_dummies(df4h["session"], prefix="sess", dtype=float, drop_first=True)
    dow_dum = pd.get_dummies(df4h["dayofweek"], prefix="dow", dtype=float, drop_first=True)
    df4h = df4h.join([sess_dum, dow_dum])

    # ---- 8) Ensure all expected dummy columns exist ----
    for col in model_feature_names:
        if col not in df4h.columns:
            df4h[col] = 0.0

    # ---- 9) range_5min from first 5 minutes of current 4H bar ----
    df1m = pd.DataFrame(m1bars).rename(
        columns={"t": "datetime", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    ).sort_values("datetime").set_index("datetime")
    if df1m.empty:
        raise ValueError("make_features_4h: m1bars is empty")

    bar_start = df4h.index[-1]   # last completed 4H bar from your aggregation
    first5 = df1m.loc[(df1m.index >= bar_start) & (df1m.index < bar_start + pd.Timedelta(minutes=5))]
    if first5.empty:
        raise ValueError("make_features_4h: missing first 5 minutes for current 4H bar")
    df4h.loc[bar_start, "range_5min"] = first5["high"].max() - first5["low"].min()

    # ---- 10) Extract the single ordered feature row ----
    if bar_start not in df4h.index:
        raise ValueError("make_features_4h: bar_start row not found in h4bars index")
    feat_row = df4h.loc[[bar_start], :]

    missing = [c for c in model_feature_names if c not in feat_row.columns]
    if missing:
        raise ValueError(f"make_features_4h: missing required features: {missing}")

    X_one = feat_row[model_feature_names].copy()

    if X_one.isna().any().any():
        na_cols = X_one.columns[X_one.isna().any()].tolist()
        raise ValueError(f"make_features_4h: NaNs present in feature row: {na_cols}")

    return X_one










class HuberWrapper:
    def __init__(self):
        self.model = None
        self.feature_names = None

    def fit(self, X, y):
        Xc = sm.add_constant(X)
        # Huber (RLM) with default tuning; you can tweak 'M' or 'scale_est'
        self.model = sm.RLM(y, Xc, M=sm.robust.norms.HuberT()).fit()
        self.feature_names = X.columns.tolist()

    def predict(self, X_new):
        X_new = X_new[self.feature_names].copy()
        Xc = sm.add_constant(X_new, has_constant='add')
        return self.model.predict(Xc)

    def summary(self):
        return self.model.summary()



# Testing & Debugging 
if __name__ == "__main__":
    from datetime import datetime
    import pytz
    import joblib
    import auth
    from data import get_hist_bars, aggregate_to_4h
    
    JWT_TOKEN = auth.authenticate()

    # Load LIVE models
    range_1h_model = joblib.load(r"C:\Users\prath\Desktop\GridVision\2. Python\ProjectX_API\huber_1h_2025-08-04.pkl")
    range_4h_model = joblib.load(r"C:\Users\prath\Desktop\GridVision\2. Python\ProjectX_API\huber_4h_2025-08-04.pkl")

    contract_id = "CON.F.US.EP.U25"

    # 1-minute bars for features & aggregation
    m1bars = get_hist_bars(contract_id, lookback_min=10000, unit=2, unit_number=1, limit=20000)
    print("len(m1bars):", len(m1bars) if m1bars else None)

    # Hourly bars for 1H features
    h1bars = get_hist_bars(contract_id, lookback_min=100*60, unit=2, unit_number=60, limit=5000)
    print("len(h1bars):", len(h1bars) if h1bars else None)

    # 4-hour bars from aggregation
    h4bars = aggregate_to_4h(m1bars)
    print("len(h4bars):", len(h4bars) if h4bars else None)

    # Current NY time (rounded to :05)
    nowNY = datetime.now(pytz.timezone("America/New_York")).replace(minute=5, second=0, microsecond=0)


    # Build 4H features & predict
    X_one_4h = make_features_4h(nowNY, m1bars, h4bars, range_4h_model.feature_names)
    pred_4h = range_4h_model.predict(X_one_4h)[0]

    print("\n=== 4H Feature Row ===")
    print(X_one_4h)
    print(f"Predicted 4H range: {pred_4h:.2f} pts")


    # Build 1H features & predict
    X_one_1h = make_features_1h(nowNY, m1bars, h1bars, range_1h_model.feature_names)
    pred_1h = range_1h_model.predict(X_one_1h)[0]

    # Print
    print("\n=== 1H Feature Row ===")
    print(X_one_1h)
    print(f"Predicted 1H range: {pred_1h:.2f} pts")

