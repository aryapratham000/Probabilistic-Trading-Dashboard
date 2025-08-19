import pandas as pd

def load_markov_matrix(path=r"C:\Users\prath\Desktop\GridVision\2. Python\ProjectX_API\colorMarkov_2step.pkl"):
    return pd.read_pickle(path)


def load_snapshots_4h():
    snapshots_df_4h = pd.read_parquet(r"C:\Users\prath\Desktop\GridVision\2. Python\ProjectX_API\df_4h_snapshots.parquet")

    # Calculate relative range quantile thresholds per session
    session_quantiles_4h = (
        snapshots_df_4h
        .groupby("session")["rel_range"]
        .quantile([0.33, 0.66])
        .unstack()
        .rename(columns={0.33: "q1", 0.66: "q2"})
        .to_dict("index")
    )

    return snapshots_df_4h, session_quantiles_4h


def load_snapshots_1h():
    snapshots_df_1h = pd.read_parquet(r"C:\Users\prath\Desktop\GridVision\2. Python\ProjectX_API\df_1h_snapshots.parquet")

    # Calculate relative range quantile thresholds per session
    session_quantiles_1h = (
        snapshots_df_1h
        .groupby("session")["rel_range"]
        .quantile([0.33, 0.66])
        .unstack()
        .rename(columns={0.33: "q1", 0.66: "q2"})
        .to_dict("index")
    )

    return snapshots_df_1h, session_quantiles_1h



def predict_next_color(mc_matrix, prev_2, prev_1):
    try:
        row = mc_matrix.loc[(prev_2, prev_1)]
        # Convert to %, remove decimals, add % sign
        formatted = row.sort_values(ascending=False).apply(lambda x: f"{int(round(x * 100))}%")
        return formatted
    except KeyError:
        return pd.Series(dtype=str)




def get_conditional_probs(snapshot, filters_enabled, df_snapshots):

    # Always apply prevColor_1 filter
    filters = (df_snapshots["prevColor_1"] == snapshot["prevColor_1"])

    for key, enabled in filters_enabled.items():
        if not enabled:
            continue

        if key == "pdHL":
            filters &= (
                (df_snapshots["pdHighTaken"] == snapshot["pdHighTaken"]) &
                (df_snapshots["pdLowTaken"] == snapshot["pdLowTaken"])
            )
        else:
            filters &= (df_snapshots[key] == snapshot[key])

    matched = df_snapshots[filters]

    if not filters_enabled.get("minute", True):
        matched = matched.sort_values("minute")
        matched = matched.drop_duplicates(subset="bar_start", keep="last")

    counts = matched["trueColor"].value_counts()

    probs = counts / counts.sum() if counts.sum() > 0 else pd.Series(dtype=float)

    return counts, probs




def build_event_probs(prob_series, prev_bar):
    # Convert Series to dict
    p = prob_series.to_dict() if hasattr(prob_series, "to_dict") else (prob_series or {})

    # Previous levels
    HP = prev_bar["h"]
    LP = prev_bar["l"]
    CP = prev_bar["c"]

    # Event probabilities (overlapping by design)
    bh = p.get("green",0) + p.get("yellow",0) + p.get("purple",0) + p.get("maroon",0)
    bl = p.get("blue",0)  + p.get("red",0)    + p.get("purple",0) + p.get("maroon",0)
    co = p.get("green",0) + p.get("blue",0)   + p.get("purple",0) + (p.get("gray",0)/2)  # close up (c>o)
    cd = p.get("yellow",0)+ p.get("red",0)    + p.get("maroon",0) + (p.get("gray",0)/2)  # close down (c<o)

    return {
        "break_over_high":  f"{int(round(bh*100))}% break over {HP:.2f}",
        "break_under_low":  f"{int(round(bl*100))}% break under {LP:.2f}",
        "close_over_close": f"{int(round(co*100))}% close over {CP:.2f}",
        "close_under_close":f"{int(round(cd*100))}% close under {CP:.2f}",
    }
