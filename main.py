#main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import auth, data
from candleClassification import classify_interaction, classify_markov, classify_session
from markov_model import load_snapshots_4h, get_conditional_probs, load_snapshots_1h, build_event_probs
from dailyLevels import initialize_daily_levels, update_live_levels
from data import latest_bar, get_hist_bars, aggregate_to_4h
from range_model import make_features_1h, make_features_4h 
import joblib
from huber_wrapper import HuberWrapper

app = FastAPI()
contract_id = "CON.F.US.EP.U25"
latest_snapshot_4h = None
latest_snapshot_1h = None
filters_enabled_4h = {
    "minute": True,
    "currColor": True,
    "prevColor_2": True,
    "session": True,
    "range_bin": False,
    "pdHL": False,
    "priceAboveNYOpen": False,
    "priceAbovePDNYOpen": False
}
filters_enabled_1h = {
    "minute": True,
    "currColor": True,
    "prevColor_2": True,
    "session": True,
    "range_bin": False,
    "pdHL": False,
    "priceAboveNYOpen": False,
    "priceAbovePDNYOpen": False
}
snapshots_df_4h, session_quantiles_4h = load_snapshots_4h()
snapshots_df_1h, session_quantiles_1h = load_snapshots_1h()
range_model_1h = joblib.load(r"C:\Users\prath\Desktop\GridVision\2. Python\ProjectX_API\huber_1h_2025-08-04.pkl")
range_model_4h = joblib.load(r"C:\Users\prath\Desktop\GridVision\2. Python\ProjectX_API\huber_4h_2025-08-04.pkl")
latest_prevbar_4h = None
latest_prevbar_1h = None


@app.websocket("/ws/stream")
async def stream_dashboard(websocket: WebSocket):
    await websocket.accept()
    JWT_TOKEN = auth.authenticate()
    dailyLevels = initialize_daily_levels(contract_id)
    await run_range_predictions(websocket)

    asyncio.create_task(stream_1min(websocket, contract_id, dailyLevels))

    while True:
        try:
            msg = await websocket.receive_json()

            if msg["type"] == "filter_request_4h":
                # Unpack inputs from frontend
                global filters_enabled_4h
                filters_enabled_4h = msg["filters_enabled"]

                if latest_snapshot_4h:
                    counts_4h, probs_4h = get_conditional_probs(
                        snapshot=latest_snapshot_4h,
                        filters_enabled=filters_enabled_4h,
                        df_snapshots=snapshots_df_4h
                    )
                
                events_4h = build_event_probs(probs_4h, latest_prevbar_4h)

                await websocket.send_json({
                    "type": "filter_update_4h",
                    "snapshot": latest_snapshot_4h,
                    "probs_4h": probs_4h.to_dict(),
                    "counts_4h": counts_4h.to_dict(),
                    "events_4h": events_4h,
                })

            if msg["type"] == "filter_request_1h":
                # Unpack inputs from frontend
                global filters_enabled_1h
                filters_enabled_1h = msg["filters_enabled"]

                if latest_snapshot_1h:
                    counts_1h, probs_1h = get_conditional_probs(
                        snapshot=latest_snapshot_1h,
                        filters_enabled=filters_enabled_1h,
                        df_snapshots=snapshots_df_1h
                    )
        
                events_1h = build_event_probs(probs_1h, latest_prevbar_1h)

                await websocket.send_json({
                    "type": "filter_update_1h",
                    "snapshot": latest_snapshot_1h,
                    "probs_1h": probs_1h.to_dict(),
                    "counts_1h": counts_1h.to_dict(),
                    "events_1h": events_1h,
                })

        except WebSocketDisconnect:
            print("⚠️ WebSocket disconnected.")
            break
        except Exception as e:
            print(f"❌ Error in message loop: {e}")





async def stream_1min(websocket, contract_id, dailyLevels):
    async for bar in latest_bar(contract_id):
        
        update_live_levels(bar, dailyLevels)

        m1bars = data.get_hist_bars(contract_id, unit=2, unit_number=1, limit=1000)
        h1bars = data.get_hist_bars(contract_id, unit=3, unit_number=1, limit=24, include_partial=True)
        h4bars = aggregate_to_4h(m1bars)
        
        print(bar["t"])
                
        prevColor_2_4h = classify_markov(h4bars[2], h4bars[3])
        prevColor1_4h = classify_markov(h4bars[1], h4bars[2])
        currColor_4h = classify_markov(h4bars[0], h4bars[1])

        prevColor_2_1h = classify_markov(h1bars[2], h1bars[3])
        prevColor1_1h = classify_markov(h1bars[1], h1bars[2])
        currColor_1h = classify_markov(h1bars[0], h1bars[1])
        
        global latest_prevbar_4h 
        global latest_prevbar_1h 
        latest_prevbar_4h = h4bars[1]
        latest_prevbar_1h = h1bars[1]

        session = classify_session(bar["t"])
        
        pdHighTaken = dailyLevels["levels"]["rollingHigh"] > dailyLevels["levels"]["pdHigh"]  
        pdLowTaken = dailyLevels["levels"]["rollingLow"] < dailyLevels["levels"]["pdLow"]
        priceAboveNYOpen = 	bar["c"] > dailyLevels["levels"]["open"]
        priceAbovePDNYOpen = bar["c"] > dailyLevels["levels"]["pdOpen"]

        curr_range_4h = h4bars[0]["h"] - h4bars[0]["l"]
        prev_range_4h = h4bars[1]["h"] - h4bars[1]["l"]
        rel_range_4h = curr_range_4h / prev_range_4h 
        q1_4h, q2_4h = session_quantiles_4h[session]["q1"], session_quantiles_4h[session]["q2"]
        if rel_range_4h < q1_4h:
            range_bin_4h = "low"
        elif rel_range_4h < q2_4h:
            range_bin_4h = "medium"
        else:
            range_bin_4h = "high"


        curr_range_1h = h1bars[0]["h"] - h1bars[0]["l"]
        prev_range_1h = h1bars[1]["h"] - h1bars[1]["l"]
        rel_range_1h = curr_range_1h / prev_range_1h 
        q1_1h, q2_1h = session_quantiles_1h[session]["q1"], session_quantiles_1h[session]["q2"]
        if rel_range_1h < q1_1h:
            range_bin_1h = "low"
        elif rel_range_1h < q2_1h:
            range_bin_1h = "medium"
        else:
            range_bin_1h = "high"


        print("bar[t]:", bar["t"])
        print("h4bars[0][t]:", h4bars[0]["t"])
        print("delta minutes:", (bar["t"] - h4bars[0]["t"]).total_seconds() // 60)

        minute_bucket_4h = int((bar["t"] - h4bars[0]["t"]).total_seconds() // 60 // 5) * 5
        minute_bucket_1h = int((bar["t"].minute//5)*5)
        
        global latest_snapshot_4h
        latest_snapshot_4h = {
            "minute": minute_bucket_4h,
            "currColor": currColor_4h,
            "prevColor_1": prevColor1_4h,
            "prevColor_2": prevColor_2_4h,
            "session": session,
            "range_bin": range_bin_4h,
            "pdHighTaken": pdHighTaken,
            "pdLowTaken": pdLowTaken,
            "priceAboveNYOpen":	priceAboveNYOpen,
            "priceAbovePDNYOpen": priceAbovePDNYOpen
        }

        global latest_snapshot_1h
        latest_snapshot_1h = {
            "minute": minute_bucket_1h,
            "currColor": currColor_1h,
            "prevColor_1": prevColor1_1h,
            "prevColor_2": prevColor_2_1h,
            "session": session,
            "range_bin": range_bin_1h,
            "pdHighTaken": pdHighTaken,
            "pdLowTaken": pdLowTaken,
            "priceAboveNYOpen":	priceAboveNYOpen,
            "priceAbovePDNYOpen": priceAbovePDNYOpen
        }

        counts_4h, probs_4h = get_conditional_probs(latest_snapshot_4h, filters_enabled_4h, snapshots_df_4h)
        counts_1h, probs_1h = get_conditional_probs(latest_snapshot_1h, filters_enabled_1h, snapshots_df_1h)

        events_4h = build_event_probs(probs_4h, latest_prevbar_4h)
        events_1h = build_event_probs(probs_1h, latest_prevbar_1h)

        interactions = []
        for level_name, level_price in dailyLevels["levels"].items():
            if level_price is None:
                continue
            interaction = classify_interaction(bar, level_price)
            if interaction:
                interactions.append((level_name, interaction))

        payload = {
            "type": "1min_tick",
            "timestamp": bar["t"].strftime("%Y-%m-%d %H:%M:%S"),
            "ohlc": {k: bar[k] for k in ("o", "h", "l", "c")},
            "interactions": interactions,
            "snapshot_4h": latest_snapshot_4h,
            "snapshot_1h": latest_snapshot_1h,
            "probs_4h": probs_4h.to_dict(),
            "counts_4h": counts_4h.to_dict(),
            "probs_1h": probs_1h.to_dict(),
            "counts_1h": counts_1h.to_dict(),
            "daily_levels": dailyLevels["levels"],
            "contract": contract_id,
            "rangeCurr_4h": curr_range_4h,
            "rangeCurr_1h": curr_range_1h,
            "events_4h": events_4h,
            "events_1h": events_1h,
        }

        await websocket.send_json(payload)
        
        if bar["t"].minute == 5:
            await run_range_predictions(websocket)

        
        
        
async def run_range_predictions(websocket):
    try:
        m1bars = get_hist_bars(contract_id, lookback_min=10000, unit=2, unit_number=1, limit=20000)
        h1bars = get_hist_bars(contract_id, lookback_min=100*60, unit=2, unit_number=60, limit=5000)
        h4bars = aggregate_to_4h(m1bars)

        # 4H Prediction
        X_one_4h = make_features_4h(m1bars, h4bars, range_model_4h.feature_names)
        pred_4h = round(float(range_model_4h.predict(X_one_4h)[0]), 2)

        # 1H Prediction
        X_one_1h = make_features_1h(m1bars, h1bars, range_model_1h.feature_names)
        pred_1h = round(float(range_model_1h.predict(X_one_1h)[0]), 2)

        # Send Payload
        payload = {
            "type": "range_prediction",
            "rangePred_1h": pred_1h,
            "rangePred_4h": pred_4h
        }

        await websocket.send_json(payload)
        print(f"📤 Sent range prediction payload: {payload}")

    except Exception as e:
        print(f"❌ Error in run_range_predictions: {e}")





