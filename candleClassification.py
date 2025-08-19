# classifiers.py

def classify_markov(bar, prev_bar) -> str:
    h, l, o, c = bar["h"], bar["l"], bar["o"], bar["c"]
    hp, lp = prev_bar["h"], prev_bar["l"]

    if h > hp and l < lp:
        return "purple" if c > o else "maroon"
    elif h > hp and l >= lp:
        return "green" if c > o else "yellow"
    elif h <= hp and l < lp:
        return "blue" if c > o else "red"
    elif h <= hp and l >= lp:
        return "gray"
    else:
        return "unknown"


def classify_interaction(bar, level) -> str:
    o, h, l, c = bar["o"], bar["h"], bar["l"], bar["c"]

    if not (l <= level <= h):
        return None

    if o < level and c > level:
        return "up_cross"
    elif o > level and c < level:
        return "down_cross"
    elif o > level and c > o:
        return "up_bounce"
    elif o < level and c < o:
        return "down_bounce"
    else:
        return "straddle_doji"


def classify_session(timestamp) -> str:
    hour = timestamp.hour
    if 2 <= hour < 6:
        return "London"
    elif 6 <= hour < 10:
        return "Pmkt"
    elif 10 <= hour < 14:
        return "Core"
    elif 14 <= hour < 18:
        return "Close"
    elif 18 <= hour < 22:
        return "Eve"
    else:
        return "Asia"

