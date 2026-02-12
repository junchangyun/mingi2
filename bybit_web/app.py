import base64
import csv
import hashlib
import hmac
import os
import threading
import time
from datetime import datetime
from typing import Any

import ccxt
import mplfinance as mpf
import pandas as pd
import requests
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_cors import CORS
from openai import OpenAI

TIMEFRAME = "15m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(BASE_DIR, "chart")
RECORD_DIR = os.path.join(BASE_DIR, "record")
CSV_PATH = os.path.join(RECORD_DIR, "trading_journal.csv")

os.makedirs(CHART_DIR, exist_ok=True)
os.makedirs(RECORD_DIR, exist_ok=True)

# OpenAI key is server-side only; never collected from UI.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

app = Flask(__name__)
CORS(app)


class MonitorState:
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_message = "대기 중"
        self.bybit_key_mask = ""


state = MonitorState()


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_chart_with_gpt(image_path: str, symbol: str, side: str) -> str:
    if not client:
        return "OPENAI_API_KEY 미설정으로 분석 생략"

    try:
        base64_image = encode_image(image_path)
        prompt_text = (
            f"이 차트는 {symbol}의 15분봉 차트다. "
            f"초록색 화살표(▲)는 Buy, 빨간색 화살표(▼)는 Sell 지점이다. "
            f"내 포지션은 {side}였다. "
            f"오직 기술적 분석 관점(캔들 패턴, 지지/저항, 추세선)에서 "
            f"진입과 청산 자리가 적절했는지 평가해줘. 핵심만 3줄 요약."
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional Technical Analyst. Focus only on chart analysis.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                        },
                    ],
                },
            ],
            max_tokens=500,
        )
        return response.choices[0].message.content or "분석 결과 없음"
    except Exception as exc:
        return f"분석 실패: {exc}"


def create_chart(exchange: ccxt.bybit, symbol: str, position_side: str, entry_time_ms: int | None, exit_time_ms: int | None, order_id: str) -> str | None:
    try:
        if entry_time_ms:
            since_time = entry_time_ms - (15 * 60 * 1000 * 10)
            ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, since=since_time)
        else:
            ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=200)

        if not ohlcv:
            return None

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        last_date = df.index[-1]
        future_dates = pd.date_range(start=last_date + pd.Timedelta(minutes=15), periods=15, freq="15min")
        future_df = pd.DataFrame(index=future_dates, columns=df.columns)
        df_extended = pd.concat([df, future_df])

        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        file_name = f"Trade_{safe_symbol}_{order_id}.png"
        save_path = os.path.join(CHART_DIR, file_name)

        buy_marker = [float("nan")] * len(df)
        sell_marker = [float("nan")] * len(df)
        offset_ratio = 0.008

        if entry_time_ms:
            entry_dt = pd.to_datetime(entry_time_ms, unit="ms")
            entry_idx = df.index.get_indexer([entry_dt], method="nearest")[0]
            if position_side == "LONG":
                buy_marker[entry_idx] = df["low"].iloc[entry_idx] * (1 - offset_ratio)
            else:
                sell_marker[entry_idx] = df["high"].iloc[entry_idx] * (1 + offset_ratio)

        if exit_time_ms:
            exit_dt = pd.to_datetime(exit_time_ms, unit="ms")
            exit_idx = df.index.get_indexer([exit_dt], method="nearest")[0]
            if position_side == "LONG":
                sell_marker[exit_idx] = df["high"].iloc[exit_idx] * (1 + offset_ratio)
            else:
                buy_marker[exit_idx] = df["low"].iloc[exit_idx] * (1 - offset_ratio)

        pad_length = len(df_extended) - len(df)
        buy_marker_extended = buy_marker + [float("nan")] * pad_length
        sell_marker_extended = sell_marker + [float("nan")] * pad_length

        add_plots = [
            mpf.make_addplot(buy_marker_extended, type="scatter", markersize=200, marker="^", color="green"),
            mpf.make_addplot(sell_marker_extended, type="scatter", markersize=200, marker="v", color="red"),
        ]

        mc = mpf.make_marketcolors(up="red", down="blue", edge="inherit", wick="inherit", volume="in")
        style = mpf.make_mpf_style(marketcolors=mc, base_mpf_style="yahoo", gridstyle="", facecolor="white")

        mpf.plot(
            df_extended,
            type="candle",
            volume=True,
            style=style,
            addplot=add_plots,
            title=symbol,
            savefig=save_path,
            figscale=1.5,
            tight_layout=True,
        )
        return save_path
    except Exception:
        return None


def save_to_csv(data: dict[str, Any]) -> None:
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        if not file_exists or os.stat(CSV_PATH).st_size == 0:
            writer.writerow([
                "거래시간",
                "주문ID",
                "종목",
                "포지션",
                "레버리지",
                "진입수량",
                "진입가",
                "청산가",
                "손익금",
                "손익률",
                "승패여부",
                "AI분석",
            ])

        writer.writerow([
            data["time"],
            data["order_id"],
            data["symbol"],
            data["side"],
            data["leverage"],
            data["qty"],
            data["entry_price"],
            data["exit_price"],
            data["pnl"],
            data["roi"],
            data["result"],
            data["ai_analysis"],
        ])


def read_recent_records(limit: int = 20) -> list[dict[str, str]]:
    if not os.path.isfile(CSV_PATH):
        return []

    rows: list[dict[str, str]] = []
    with open(CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            rows.append(row)

    return rows[-limit:][::-1]


def get_leverage(exchange: ccxt.bybit, symbol: str) -> float:
    try:
        positions = exchange.fetch_positions([symbol])
        if positions:
            return float(positions[0].get("leverage") or 1)
    except Exception:
        return 1
    return 1


SENSITIVE_PERMISSION_KEYWORDS = (
    "withdraw",
    "deposit",
    "transfer",
    "wallettransfer",
    "asset",
)


def _is_truthy_permission_text(text: str) -> bool:
    return text not in {"", "0", "false", "none", "off", "no", "null"}


def _contains_sensitive_permission(value: Any) -> bool:
    if isinstance(value, dict):
        for k, v in value.items():
            key_lower = str(k).lower()
            val_lower = str(v).lower().strip()
            if any(keyword in key_lower for keyword in SENSITIVE_PERMISSION_KEYWORDS) and _is_truthy_permission_text(val_lower):
                return True
            if _contains_sensitive_permission(v):
                return True
    elif isinstance(value, list):
        for item in value:
            if _contains_sensitive_permission(item):
                return True
    else:
        text = str(value).lower().strip()
        if any(keyword in text for keyword in SENSITIVE_PERMISSION_KEYWORDS) and _is_truthy_permission_text(text):
            return True
    return False


def verify_no_withdraw_permission(api_key: str, api_secret: str) -> tuple[bool, str]:
    """Bybit V5 API key info 조회 후 입출금/전송 관련 권한이 있으면 거부."""
    try:
        ts = str(int(time.time() * 1000))
        recv_window = "5000"
        payload = f"{ts}{api_key}{recv_window}"
        signature = hmac.new(api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

        headers = {
            "X-BAPI-API-KEY": api_key,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
        }

        resp = requests.get("https://api.bybit.com/v5/user/query-api", headers=headers, timeout=10)
        data = resp.json()

        if data.get("retCode") != 0:
            return False, f"Bybit 키 검증 실패: {data.get('retMsg', '알 수 없는 오류')}"

        result = data.get("result", {})
        if _contains_sensitive_permission(result):
            return False, "입출금/전송 권한이 있는 API 키는 허용되지 않습니다. 거래 전용 키를 사용하세요."

        return True, "검증 완료: 입출금/전송 권한 없음"
    except Exception as exc:
        return False, f"키 권한 확인 실패: {exc}"


def run_monitor(bybit_key: str, bybit_secret: str) -> None:
    state.running = True
    state.bybit_key_mask = mask_key(bybit_key)
    state.last_message = "모니터 시작"

    exchange = ccxt.bybit(
        {
            "apiKey": bybit_key,
            "secret": bybit_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }
    )

    last_order_id = None
    try:
        orders = exchange.fetch_closed_orders(limit=1)
        if orders:
            last_order_id = orders[0]["id"]
    except Exception as exc:
        state.last_message = f"초기 주문 조회 실패: {exc}"

    while state.running:
        try:
            orders = exchange.fetch_closed_orders(limit=1)
            if not orders:
                time.sleep(1)
                continue

            latest_order = orders[0]
            current_id = latest_order["id"]
            if current_id == last_order_id:
                time.sleep(1)
                continue

            symbol = latest_order["symbol"]
            order_side = latest_order["side"]
            position_side = "LONG" if order_side.lower() == "sell" else "SHORT"

            leverage = get_leverage(exchange, symbol)
            trades = exchange.fetch_my_trades(symbol, limit=100)

            pnl = 0.0
            qty = float(latest_order.get("amount") or 0)
            exit_price = float(latest_order.get("price") or 0)
            entry_price = exit_price
            exit_time_ms = latest_order.get("timestamp")
            entry_time_ms = None

            if trades:
                closing_trade = next((t for t in reversed(trades) if t.get("order") == latest_order.get("id")), None)
                if closing_trade:
                    info = closing_trade.get("info", {})
                    if "closedPnl" in info:
                        pnl = float(info["closedPnl"])
                    if "execPrice" in info:
                        exit_price = float(info["execPrice"])
                    if "execQty" in info:
                        qty = float(info["execQty"])
                    exit_time_ms = closing_trade.get("timestamp")

                entry_side = "buy" if position_side == "LONG" else "sell"
                opening_trade = next(
                    (
                        t
                        for t in reversed(trades)
                        if t.get("timestamp") and exit_time_ms and t["timestamp"] < exit_time_ms and t.get("side") == entry_side
                    ),
                    None,
                )
                if opening_trade:
                    entry_price = float(opening_trade.get("price") or entry_price)
                    entry_time_ms = opening_trade.get("timestamp")

            if entry_time_ms is None and qty > 0:
                if position_side == "LONG":
                    entry_price = exit_price - (pnl / qty)
                else:
                    entry_price = exit_price + (pnl / qty)

            margin = (entry_price * qty) / float(leverage or 1)
            roi = (pnl / margin) * 100 if margin > 0 else 0
            result_str = "WIN" if pnl > 0 else "LOSE"

            chart_path = create_chart(exchange, symbol, position_side, entry_time_ms, exit_time_ms, str(current_id))
            ai_comment = "분석 생략"
            if chart_path:
                ai_comment = analyze_chart_with_gpt(chart_path, symbol, position_side)

            save_to_csv(
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "order_id": current_id,
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
                }
            )

            state.last_message = f"저장 완료: {symbol} {result_str} PnL {pnl}"
            last_order_id = current_id
            time.sleep(1)

        except Exception as exc:
            state.last_message = f"에러 (재시도): {exc}"
            time.sleep(1)

    state.last_message = "모니터 중지"


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        running=state.running,
        status=state.last_message,
        key_mask=state.bybit_key_mask,
    )


@app.route("/start", methods=["POST"])
def start_monitor():
    if state.running:
        return redirect(url_for("index"))

    bybit_key = (request.form.get("bybit_api_key") or "").strip()
    bybit_secret = (request.form.get("bybit_secret_key") or "").strip()

    if not bybit_key or not bybit_secret:
        state.last_message = "Bybit API Key/Secret을 모두 입력하세요."
        return redirect(url_for("index"))

    ok, message = verify_no_withdraw_permission(bybit_key, bybit_secret)
    if not ok:
        state.last_message = message
        return redirect(url_for("index"))

    state.thread = threading.Thread(target=run_monitor, args=(bybit_key, bybit_secret), daemon=True)
    state.thread.start()
    state.last_message = "모니터링 시작됨"
    return redirect(url_for("index"))


@app.route("/stop", methods=["POST"])
def stop_monitor():
    state.running = False
    return redirect(url_for("index"))


@app.route("/status", methods=["GET"])
def status():
    return jsonify(
        {
            "running": state.running,
            "status": state.last_message,
            "key_mask": state.bybit_key_mask,
            "recent": read_recent_records(10),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
