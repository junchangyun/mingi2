import os, time, csv, threading
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

import ccxt
import pandas as pd
import mplfinance as mpf
import base64
from openai import OpenAI

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(BASE_DIR, "chart")
RECORD_DIR = os.path.join(BASE_DIR, "record")
CSV_PATH = os.path.join(RECORD_DIR, "trading_journal.csv")

os.makedirs(CHART_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)

# ===== 전역 상태(단일 사용자 MVP용) =====
STATE = {
    "running": False,
    "last_msg": "idle",
    "key_mask": "-",
    "thread": None,
    "stop_event": threading.Event(),
    "recent": []  # 최근 10건 (dict)
}

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # 서버 환경변수로!
TIMEFRAME = "15m"


def mask_key(k: str) -> str:
    if not k:
        return "-"
    if len(k) <= 8:
        return k[:2] + "***"
    return k[:4] + "..." + k[-4:]


def save_to_csv_row(row: dict):
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if (not file_exists) or os.stat(CSV_PATH).st_size == 0:
            w.writerow(["거래시간", "주문ID", "종목", "포지션", "레버리지", "진입수량", "진입가", "청산가", "손익금", "손익률", "승패여부", "AI분석", "차트파일"])
        w.writerow([
            row["time"],
            row["order_id"],
            row["symbol"],
            row["side"],
            row["leverage"],
            row["qty"],
            row["entry_price"],
            row["exit_price"],
            row["pnl"],
            row["roi"],
            row["result"],
            row["ai_analysis"],
            row["chart_file"],
        ])


def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_chart_with_gpt(client: OpenAI, image_path, symbol, side):
    if not client:
        return "분석 생략(OpenAI 미설정)"
    try:
        b64 = encode_image(image_path)
        prompt_text = (
            f"이 차트는 {symbol}의 15분봉 차트다. "
            f"초록색 화살표(▲)는 Buy, 빨간색 화살표(▼)는 Sell 지점이다. "
            f"내 포지션은 {side}였다. "
            f"오직 기술적 분석 관점(캔들 패턴, 지지/저항, 추세선)에서 "
            f"진입과 청산 자리가 적절했는지 평가해줘. 핵심만 3줄 요약."
        )
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional Technical Analyst. Focus only on chart analysis."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                },
            ],
            max_tokens=500,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"분석 실패: {e}"


def create_chart(exchange, symbol, position_side, entry_time_ms, exit_time_ms, order_id):
    try:
        if entry_time_ms:
            since_time = entry_time_ms - (15 * 60 * 1000 * 10)
            ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, since=since_time)
        else:
            ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=200)

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        last_date = df.index[-1]
        future_dates = pd.date_range(start=last_date + pd.Timedelta(minutes=15), periods=15, freq="15min")
        future_df = pd.DataFrame(index=future_dates, columns=df.columns)
        df_ext = pd.concat([df, future_df])

        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        file_name = f"Trade_{safe_symbol}_{order_id}.png"
        save_path = os.path.join(CHART_DIR, file_name)

        buy_marker = [float("nan")] * len(df)
        sell_marker = [float("nan")] * len(df)
        offset_ratio = 0.008

        if entry_time_ms:
            entry_dt = pd.to_datetime(entry_time_ms, unit="ms")
            idx = df.index.get_indexer([entry_dt], method="nearest")[0]
            if position_side == "LONG":
                buy_marker[idx] = df["low"].iloc[idx] * (1 - offset_ratio)
            else:
                sell_marker[idx] = df["high"].iloc[idx] * (1 + offset_ratio)

        if exit_time_ms:
            exit_dt = pd.to_datetime(exit_time_ms, unit="ms")
            idx = df.index.get_indexer([exit_dt], method="nearest")[0]
            if position_side == "LONG":
                sell_marker[idx] = df["high"].iloc[idx] * (1 + offset_ratio)
            else:
                buy_marker[idx] = df["low"].iloc[idx] * (1 - offset_ratio)

        pad = len(df_ext) - len(df)
        buy_ext = buy_marker + [float("nan")] * pad
        sell_ext = sell_marker + [float("nan")] * pad

        add_plots = [
            mpf.make_addplot(buy_ext, type="scatter", markersize=200, marker="^", color="green"),
            mpf.make_addplot(sell_ext, type="scatter", markersize=200, marker="v", color="red"),
        ]

        mc = mpf.make_marketcolors(up="red", down="blue", edge="inherit", wick="inherit", volume="in")
        style = mpf.make_mpf_style(marketcolors=mc, base_mpf_style="yahoo", gridstyle="", facecolor="white")

        mpf.plot(
            df_ext,
            type="candle",
            volume=True,
            style=style,
            addplot=add_plots,
            title=symbol,
            savefig=save_path,
            figscale=1.5,
            tight_layout=True,
        )

        return file_name  # 파일명만 반환(서빙용)
    except Exception as e:
        STATE["last_msg"] = f"차트 생성 실패: {e}"
        return None


def get_leverage(exchange, symbol):
    try:
        pos = exchange.fetch_positions([symbol])
        if pos:
            return pos[0].get("leverage", 1) or 1
    except Exception:
        pass
    return 1


def monitor_loop(api_key: str, secret: str):
    STATE["last_msg"] = "모니터 시작됨"
    STATE["running"] = True
    STATE["stop_event"].clear()

    exchange = ccxt.bybit(
        {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }
    )

    client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

    last_order_id = None
    try:
        orders = exchange.fetch_closed_orders(limit=1)
        if orders:
            last_order_id = orders[0]["id"]
    except Exception:
        pass

    while not STATE["stop_event"].is_set():
        try:
            orders = exchange.fetch_closed_orders(limit=1)
            if not orders:
                time.sleep(1)
                continue

            latest = orders[0]
            oid = latest["id"]
            if oid == last_order_id:
                time.sleep(1)
                continue

            symbol = latest["symbol"]
            order_side = latest["side"]  # buy/sell
            position_side = "LONG" if order_side.lower() == "sell" else "SHORT"

            time.sleep(2)

            leverage = get_leverage(exchange, symbol)
            trades = exchange.fetch_my_trades(symbol, limit=100)

            pnl = 0.0
            qty = float(latest["amount"])
            exit_price = float(latest["price"])
            entry_price = exit_price
            exit_time_ms = latest["timestamp"]
            entry_time_ms = None

            if trades:
                closing_trade = next((t for t in reversed(trades) if t.get("order") == oid), None)
                if closing_trade:
                    info = closing_trade.get("info", {}) or {}
                    if "closedPnl" in info:
                        pnl = float(info["closedPnl"])
                    if "execPrice" in info:
                        exit_price = float(info["execPrice"])
                    if "execQty" in info:
                        qty = float(info["execQty"])
                    exit_time_ms = closing_trade["timestamp"]

                entry_side = "buy" if position_side == "LONG" else "sell"
                opening_trade = next(
                    (t for t in reversed(trades) if t["timestamp"] < exit_time_ms and t["side"] == entry_side),
                    None,
                )
                if opening_trade:
                    entry_price = opening_trade["price"]
                    entry_time_ms = opening_trade["timestamp"]

            if entry_time_ms is None and qty > 0:
                if position_side == "LONG":
                    entry_price = exit_price - (pnl / qty)
                else:
                    entry_price = exit_price + (pnl / qty)

            margin = (entry_price * qty) / float(leverage)
            roi = (pnl / margin) * 100 if margin > 0 else 0
            result_str = "WIN" if pnl > 0 else "LOSE"

            chart_file = create_chart(exchange, symbol, position_side, entry_time_ms, exit_time_ms, oid)
            ai_comment = "분석 생략"
            if chart_file:
                image_path = os.path.join(CHART_DIR, chart_file)
                ai_comment = analyze_chart_with_gpt(client, image_path, symbol, position_side)

            row = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "order_id": oid,
                "symbol": symbol,
                "side": position_side,
                "leverage": leverage,
                "qty": qty,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "roi": f"{roi:.2f}%",
                "result": result_str,
                "ai_analysis": ai_comment,
                "chart_file": chart_file or "",
            }

            # 최근 10건 메모리 저장 + CSV 저장
            STATE["recent"] = ([row] + STATE["recent"])[:10]
            save_to_csv_row(row)

            STATE["last_msg"] = f"기록 완료: {symbol} {result_str}"
            last_order_id = oid

        except Exception as e:
            STATE["last_msg"] = f"에러(계속): {e}"
            time.sleep(1)

    STATE["running"] = False
    STATE["last_msg"] = "모니터 중지됨"


@app.post("/start")
def start():
    if STATE["running"]:
        return jsonify({"ok": True, "msg": "이미 실행 중"})

    api_key = request.form.get("bybit_api_key", "").strip()
    secret = request.form.get("bybit_secret_key", "").strip()

    if not api_key or not secret:
        return jsonify({"ok": False, "error": "키/시크릿 누락"}), 400

    STATE["key_mask"] = mask_key(api_key)

    t = threading.Thread(target=monitor_loop, args=(api_key, secret), daemon=True)
    STATE["thread"] = t
    t.start()

    return jsonify({"ok": True})


@app.post("/stop")
def stop():
    STATE["stop_event"].set()
    return jsonify({"ok": True})


@app.get("/status")
def status():
    return jsonify({
        "running": STATE["running"],
        "key_mask": STATE["key_mask"],
        "status": STATE["last_msg"],
    })


@app.get("/recent")
def recent():
    return jsonify({"items": STATE["recent"]})


@app.get("/chart/<path:filename>")
def chart(filename):
    return send_from_directory(CHART_DIR, filename)


# health check
@app.get("/")
def root():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
