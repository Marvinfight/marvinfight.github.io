#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关岭 / 贵阳 风速数据管道（Open-Meteo → 本地 SQLite → 回写报告）

站点坐标（按地理编码确定，可在 LOCATIONS 中修改）：
    关岭  25.95N, 105.62E
    贵阳  26.65N, 106.63E

数据来源（Open-Meteo）：
    forecast             https://api.open-meteo.com/v1/forecast
                         实时/未来预报，用于「申报日」当天风速
    historical_forecast  https://historical-forecast-api.open-meteo.com/v1/forecast
                         历史「当时的预报」，可用于相似日
    archive              https://archive-api.open-meteo.com/v1/archive
                         ERA5 历史实测，用于相似日（默认）

本地数据库：guizhou/weather.db（SQLite）
    表 locations   —— 站点坐标
    表 wind_hourly —— 逐小时风速（date, location, hour, source 唯一）

用法：
    python wind_db.py init                                    # 建库
    python wind_db.py fetch --report report_2026-09-15.html    # 按报告里的日期抓取风速
    python wind_db.py fetch --start 2026-08-01 --end 2026-09-15
    python wind_db.py fetch --report report_2026-09-15.html --source archive
    python wind_db.py show --date 2026-09-15 --location 关岭
    python wind_db.py inject --report report_2026-09-15.html   # 用库中数据回写报告风速
"""

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "weather.db"
TIMEZONE = "Asia/Shanghai"
WIND_UNIT = "ms"  # m/s，与报告内嵌数据口径一致（Open-Meteo 默认是 km/h）

# 站点坐标
LOCATIONS = {
    "关岭": {"lat": 25.95, "lon": 105.62},
    "贵阳": {"lat": 26.65, "lon": 106.63},
}

# 报告 JSON 中的字段 -> 站点名
REPORT_FIELDS = {
    "weather_w": "关岭",
    "weather_g": "贵阳",
}

# 相似日在 weather_xx 数组中的风速下标（顺序：温度/湿度/云量/降水/风速/辐射）
WIND_INDEX_IN_SIMILAR = 4

ENDPOINTS = {
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "historical_forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "archive": "https://archive-api.open-meteo.com/v1/archive",
}

# 默认抓取策略：申报日用预报，相似日用历史实测
DEFAULT_SOURCE = {"target": "forecast", "similar": "archive"}


# ─────────────────────────────────────────────────────────────
# 数据库
# ─────────────────────────────────────────────────────────────


def open_db(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS locations (
            name TEXT PRIMARY KEY,
            lat  REAL NOT NULL,
            lon  REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wind_hourly (
            date          TEXT NOT NULL,
            location      TEXT NOT NULL,
            hour          INTEGER NOT NULL,
            wind_speed_10m REAL,
            source        TEXT NOT NULL,
            fetched_at    TEXT NOT NULL,
            PRIMARY KEY (date, location, hour, source)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_wind_date_loc ON wind_hourly (date, location)"
    )
    for name, loc in LOCATIONS.items():
        conn.execute(
            "INSERT OR REPLACE INTO locations (name, lat, lon) VALUES (?, ?, ?)",
            (name, loc["lat"], loc["lon"]),
        )
    conn.commit()
    return conn


def upsert_wind(conn, rows):
    """rows: (date, location, hour, speed, source)"""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.executemany(
        """
        INSERT OR REPLACE INTO wind_hourly
            (date, location, hour, wind_speed_10m, source, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [(d, loc, h, v, src, now) for (d, loc, h, v, src) in rows],
    )
    conn.commit()
    return len(rows)


def get_series(conn, day, location, source):
    """取某站某日 24 小时风速；缺失返回 None。"""
    cur = conn.execute(
        """
        SELECT hour, wind_speed_10m FROM wind_hourly
        WHERE date = ? AND location = ? AND source = ?
        ORDER BY hour
        """,
        (day, location, source),
    )
    found = dict(cur.fetchall())
    if not found:
        return None
    return [found.get(h) for h in range(24)]


# ─────────────────────────────────────────────────────────────
# Open-Meteo
# ─────────────────────────────────────────────────────────────


def _ssl_context(verify=True):
    import ssl

    if verify:
        try:
            import certifi  # 若已安装则用它的证书链
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:  # noqa: BLE001
            return ssl.create_default_context()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_json(url, params, retries=3, timeout=30):
    import ssl

    query = urllib.parse.urlencode(params)
    full = f"{url}?{query}"
    last_err = None
    verify = True
    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "wind-db/1.0"})
            with urllib.request.urlopen(
                req, timeout=timeout, context=_ssl_context(verify)
            ) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if "error" in payload and payload["error"]:
                raise RuntimeError(payload.get("reason") or payload["error"])
            return payload
        except ssl.SSLCertVerificationError as exc:
            # 部分环境（如自带 python）缺少根证书链，降级为不校验后重试一次
            if verify:
                verify = False
                print("  [warn] TLS 证书校验失败，改用不校验模式重试（可 pip install certifi 消除此提示）")
                attempt -= 1
                continue
            last_err = exc
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        if attempt < retries:
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"请求 Open-Meteo 失败：{url} -> {last_err}")


def fetch_wind(conn, location, start, end, source):
    """抓取 [start, end] 区间的小时风速并入库，返回写入条数。"""
    if location not in LOCATIONS:
        raise SystemExit(f"未知站点：{location}（可选 {', '.join(LOCATIONS)}）")
    if source not in ENDPOINTS:
        raise SystemExit(f"未知数据源：{source}（可选 {', '.join(ENDPOINTS)}）")

    loc = LOCATIONS[location]
    payload = http_json(
        ENDPOINTS[source],
        {
            "latitude": loc["lat"],
            "longitude": loc["lon"],
            "hourly": "wind_speed_10m",
            "start_date": start,
            "end_date": end,
            "wind_speed_unit": WIND_UNIT,
            "timezone": TIMEZONE,
        },
    )
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    speeds = hourly.get("wind_speed_10m") or []

    rows = []
    for stamp, speed in zip(times, speeds):
        day, _, clock = stamp.partition("T")
        rows.append((day, location, int(clock[:2]), speed, source))
    return upsert_wind(conn, rows)


# ─────────────────────────────────────────────────────────────
# 报告读写
# ─────────────────────────────────────────────────────────────


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


D_JSON_RE = re.compile(r"(const D = )(\{.*?\n\});", re.S)


def load_report(path):
    text = read_text(path)
    match = D_JSON_RE.search(text)
    if not match:
        raise SystemExit(f"未在 {path} 中找到 `const D = {{...}};` 数据块")
    return text, match, json.loads(match.group(2))


def report_dates(data):
    """返回 (申报日, [相似日...])"""
    target = data["target_date"]
    similar = [s["date"] for s in data.get("similar_days", [])]
    return target, similar


def cmd_init(args):
    conn = open_db(args.db)
    conn.close()
    print(f"已创建/校验数据库：{args.db}")
    print("  站点：")
    for name, loc in LOCATIONS.items():
        print(f"    {name}  {loc['lat']}N, {loc['lon']}E")
    return 0


def cmd_fetch(args):
    conn = open_db(args.db)

    tasks = []  # (start, end, source, label)
    if args.report:
        _, _, data = load_report(args.report)
        target, similar = report_dates(data)
        if target:
            tasks.append((target, target, args.source or DEFAULT_SOURCE["target"], "申报日"))
        for day in similar:
            tasks.append((day, day, args.source or DEFAULT_SOURCE["similar"], "相似日"))
    elif args.start and args.end:
        tasks.append((args.start, args.end, args.source or DEFAULT_SOURCE["target"], "区间"))
    else:
        raise SystemExit("请提供 --report，或 --start 与 --end")

    if not tasks:
        print("没有需要抓取的日期")
        return 0

    total = 0
    for start, end, source, label in tasks:
        for location in LOCATIONS:
            try:
                count = fetch_wind(conn, location, start, end, source)
                total += count
                print(f"  [{label}] {start} {location} <- {source}：写入 {count} 条")
            except Exception as exc:  # noqa: BLE001
                print(f"  [{label}] {start} {location} <- {source}：失败（{exc}）")
    conn.close()
    print(f"完成，共写入 {total} 条记录。")
    return 0


def cmd_show(args):
    conn = open_db(args.db)
    where, params = [], []
    if args.date:
        where.append("date = ?")
        params.append(args.date)
    if args.location:
        where.append("location = ?")
        params.append(args.location)
    if args.source:
        where.append("source = ?")
        params.append(args.source)
    sql = "SELECT date, location, source, COUNT(*), ROUND(AVG(wind_speed_10m), 2) FROM wind_hourly"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY date, location, source ORDER BY date, location, source"
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("（无记录）")
    else:
        print(f"{'日期':<12}{'站点':<8}{'数据源':<20}{'小时数':<8}{'平均风速(m/s)'}")
        for day, location, source, count, avg in rows:
            print(f"{day:<12}{location:<8}{source:<20}{count:<8}{avg}")
    conn.close()
    return 0


def cmd_inject(args):
    conn = open_db(args.db)
    text, match, data = load_report(args.report)
    target, similar = report_dates(data)

    changed = []

    # 申报日：weather_w / weather_g 的 wind
    for field, location in REPORT_FIELDS.items():
        series = get_series(conn, target, location, args.target_source)
        if series is None:
            print(f"  跳过 {target} {location}（库中无 {args.target_source} 数据）")
            continue
        data[field]["wind"] = series
        changed.append(f"{target} {location}.wind")

    # 相似日：weather_w / weather_g 第 5 个数组（下标 4）
    for day_data in data.get("similar_days", []):
        day = day_data["date"]
        for field, location in REPORT_FIELDS.items():
            series = get_series(conn, day, location, args.similar_source)
            if series is None:
                print(f"  跳过 {day} {location}（库中无 {args.similar_source} 数据）")
                continue
            day_data[field][WIND_INDEX_IN_SIMILAR] = series
            changed.append(f"{day} {location}.weather[{WIND_INDEX_IN_SIMILAR}]")

    if not changed:
        print("没有可回写的数据，文件未改动。")
        conn.close()
        return 0

    new_json = json.dumps(data, ensure_ascii=False, indent=2)
    new_text = text[: match.start(2)] + new_json + text[match.end(2) :]
    write_text(args.report, new_text)

    print(f"已回写 {len(changed)} 处风速：")
    for item in changed:
        print(f"  - {item}")
    conn.close()
    return 0


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(
        description="关岭/贵阳风速数据管道（Open-Meteo → SQLite → 报告）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--db", default=str(DEFAULT_DB), help=f"SQLite 文件路径（默认 {DEFAULT_DB.name}）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="创建本地数据库")

    p_fetch = sub.add_parser("fetch", help="从 Open-Meteo 抓取风速并入库")
    p_fetch.add_argument("--report", help="按报告里的申报日/相似日抓取")
    p_fetch.add_argument("--start", help="起始日期 YYYY-MM-DD")
    p_fetch.add_argument("--end", help="结束日期 YYYY-MM-DD")
    p_fetch.add_argument(
        "--source",
        choices=list(ENDPOINTS),
        help="数据源；按报告抓取时默认：申报日 forecast、相似日 archive",
    )

    p_show = sub.add_parser("show", help="查看库中数据")
    p_show.add_argument("--date")
    p_show.add_argument("--location", choices=list(LOCATIONS))
    p_show.add_argument("--source", choices=list(ENDPOINTS))

    p_inject = sub.add_parser("inject", help="用库中数据回写报告的风速数组")
    p_inject.add_argument("--report", required=True)
    p_inject.add_argument(
        "--target-source", default=DEFAULT_SOURCE["target"], choices=list(ENDPOINTS),
        help="申报日取哪个数据源（默认 forecast）",
    )
    p_inject.add_argument(
        "--similar-source", default=DEFAULT_SOURCE["similar"], choices=list(ENDPOINTS),
        help="相似日取哪个数据源（默认 archive，即历史实测）",
    )

    args = ap.parse_args()
    handlers = {"init": cmd_init, "fetch": cmd_fetch, "show": cmd_show, "inject": cmd_inject}
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
