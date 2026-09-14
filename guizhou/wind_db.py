#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关岭 / 贵阳 逐小时天气数据管道（Open-Meteo → 本地 SQLite → 回写报告）

站点坐标（按地理编码确定，可在 LOCATIONS 中修改）：
    关岭  25.95N, 105.62E   —— 报告中的 weather_w
    贵阳  26.65N, 106.63E   —— 报告中的 weather_g

采集要素（与报告字段一一对应）：
    temp   温度        temperature_2m
    hum    相对湿度    relative_humidity_2m
    cloud  云量        cloud_cover
    precip 降水        precipitation
    wind   风速        wind_speed_10m      (m/s)
    rad    短波辐射    shortwave_radiation (W/m²)

数据源（Open-Meteo，按角色自动回退）：
    forecast             https://api.open-meteo.com/v1/forecast       实时/未来预报
    historical_forecast  https://historical-forecast-api.open-meteo.com/v1/forecast  历史当时的预报
    archive              https://archive-api.open-meteo.com/v1/archive  ERA5 历史实测
    申报日默认顺序：forecast → historical_forecast → archive
    相似日默认顺序：archive  → historical_forecast → forecast
    （老报告日期超出预报接口范围、或近几日尚无 ERA5 实测时，会自动换源，保证数据完整）

本地数据库：guizhou/weather.db（SQLite）
    locations       站点坐标
    weather_hourly  逐小时全要素（date, location, hour, source 唯一）

用法：
    python wind_db.py init                                       # 建库
    python wind_db.py plan --detail                               # 只统计有多少日期要补（不联网）
    python wind_db.py fetch --report report_2026-09-15.html       # 按报告日期抓全要素
    python wind_db.py fetch --start 2026-08-01 --end 2026-09-15   # 指定区间
    python wind_db.py show                                        # 数据概览
    python wind_db.py show --date 2026-09-08 --location 关岭       # 某日某站逐小时明细
    python wind_db.py inject --report report_2026-09-15.html       # 回写报告（缺失可 --ensure 自动补）
    python wind_db.py sync report_a.html report_b.html            # 补数 + 回写
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

# 报告字段 -> 站点（关岭已作为 weather_w 的数据源）
REPORT_FIELDS = {
    "weather_w": "关岭",
    "weather_g": "贵阳",
}

# 报告字段 -> Open-Meteo 变量
VARIABLES = {
    "temp": "temperature_2m",
    "hum": "relative_humidity_2m",
    "cloud": "cloud_cover",
    "precip": "precipitation",
    "wind": "wind_speed_10m",
    "rad": "shortwave_radiation",
}

# 相似日 weather_xx 为数组，顺序与下面一致：温度/湿度/云量/降水/风速/辐射
VARIABLE_ORDER = ["temp", "hum", "cloud", "precip", "wind", "rad"]

ENDPOINTS = {
    "forecast": "https://api.open-meteo.com/v1/forecast",
    "historical_forecast": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    "archive": "https://archive-api.open-meteo.com/v1/archive",
}

# 按角色的数据源优先级（前面的取不到时自动回退）
SOURCE_PRIORITY = {
    "target": ["forecast", "historical_forecast", "archive"],
    "similar": ["archive", "historical_forecast", "forecast"],
}


# ─────────────────────────────────────────────────────────────
# 数据库
# ─────────────────────────────────────────────────────────────


def open_db(db_path=None):
    conn = sqlite3.connect(str(db_path or DEFAULT_DB))
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
        CREATE TABLE IF NOT EXISTS weather_hourly (
            date       TEXT NOT NULL,
            location   TEXT NOT NULL,
            hour       INTEGER NOT NULL,
            source     TEXT NOT NULL,
            temp       REAL,
            hum        REAL,
            cloud      REAL,
            precip     REAL,
            wind       REAL,
            rad        REAL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (date, location, hour, source)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_weather_date_loc ON weather_hourly (date, location)"
    )
    # 旧版只存风速的表，如存在则清理（结构已被 weather_hourly 取代）
    conn.execute("DROP TABLE IF EXISTS wind_hourly")
    for name, loc in LOCATIONS.items():
        conn.execute(
            "INSERT OR REPLACE INTO locations (name, lat, lon) VALUES (?, ?, ?)",
            (name, loc["lat"], loc["lon"]),
        )
    conn.commit()
    return conn


def upsert_weather(conn, rows):
    """rows: (date, location, hour, source, temp, hum, cloud, precip, wind, rad)"""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.executemany(
        """
        INSERT OR REPLACE INTO weather_hourly
            (date, location, hour, source, temp, hum, cloud, precip, wind, rad, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [tuple(r) + (now,) for r in rows],
    )
    conn.commit()
    return len(rows)


def get_series(conn, day, location, source, variable):
    """取某站某日某源某要素的 24 小时序列；无数据返回 None。"""
    if variable not in VARIABLES:
        raise ValueError(f"未知要素：{variable}")
    cur = conn.execute(
        f"""
        SELECT hour, {variable} FROM weather_hourly
        WHERE date = ? AND location = ? AND source = ?
        ORDER BY hour
        """,
        (day, location, source),
    )
    found = dict(cur.fetchall())
    if not found:
        return None
    return [found.get(h) for h in range(24)]


def pick_series(conn, day, location, role, variable, override=None):
    """按角色优先级取序列，命中即返回；都没有返回 None。"""
    sources = [override] if override else SOURCE_PRIORITY[role]
    for src in sources:
        series = get_series(conn, day, location, src, variable)
        if series is not None:
            return series
    return None


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
            req = urllib.request.Request(full, headers={"User-Agent": "weather-db/1.0"})
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


def fetch_weather(conn, location, start, end, source):
    """抓取 [start, end] 区间的全要素小时数据并入库，返回写入条数。"""
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
            "hourly": ",".join(VARIABLES.values()),
            "start_date": start,
            "end_date": end,
            "wind_speed_unit": WIND_UNIT,
            "timezone": TIMEZONE,
        },
    )
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    column_series = {key: hourly.get(api_name) or [] for key, api_name in VARIABLES.items()}

    rows = []
    for idx, stamp in enumerate(times):
        day, _, clock = stamp.partition("T")
        values = [
            column_series[key][idx] if idx < len(column_series[key]) else None
            for key in VARIABLE_ORDER
        ]
        rows.append((day, location, int(clock[:2]), source, *values))
    if not rows:
        raise RuntimeError(f"{source} 未返回数据（{start}~{end} {location}）")
    return upsert_weather(conn, rows)


def ensure_day(conn, day, location, role, force=False):
    """确保某日某站数据已入库；返回 (使用的源, 写入条数)。"""
    sources = SOURCE_PRIORITY[role]
    if not force:
        for src in sources:
            if get_series(conn, day, location, src, "temp") is not None:
                return src, 0

    errors = []
    for src in sources:
        try:
            count = fetch_weather(conn, location, day, day, src)
            return src, count
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{src}: {exc}")
    raise RuntimeError("全部数据源均失败 -> " + " | ".join(errors))


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


# ─────────────────────────────────────────────────────────────
# 批量准备：扫描 → 规划 → 按需补抓（最小化 API 调用）
# ─────────────────────────────────────────────────────────────

ROLE_ORDER = ("target", "similar")

# 预报接口的可回溯窗口（天）；更早的日期直接用历史预报接口
FORECAST_WINDOW_DAYS = 92
# 合并日期区间时允许的最大空隙（天），空隙内多抓几天无害且能显著减少调用
MAX_GAP_DAYS = 7


def _primary_source(role, day):
    """该日期该角色首选哪个数据源。"""
    if role == "target":
        try:
            age = (dt.date.today() - dt.date.fromisoformat(day)).days
        except ValueError:
            return SOURCE_PRIORITY[role][0]
        return "forecast" if age <= FORECAST_WINDOW_DAYS else "historical_forecast"
    return SOURCE_PRIORITY[role][0]


def _merge_ranges(days, max_gap_days=MAX_GAP_DAYS):
    """把日期列表合并为连续区间（空隙不超过 max_gap_days 时并成一段）。"""
    merged = []
    for day in sorted(days):
        if merged:
            last_end = dt.date.fromisoformat(merged[-1][1])
            if (dt.date.fromisoformat(day) - last_end).days <= max_gap_days:
                merged[-1][1] = day
                continue
        merged.append([day, day])
    return [tuple(pair) for pair in merged]


def group_requests(missing, max_gap_days=MAX_GAP_DAYS):
    """
    把缺失清单按 (角色, 站点, 首选数据源) 分组，再把日期合并成区间。
    返回 [(角色, 站点, 首选源, 起, 止)]，长度即为最少调用次数。
    """
    groups = {}
    for day, role, location in missing:
        key = (role, location, _primary_source(role, day))
        groups.setdefault(key, []).append(day)

    requests = []
    for (role, location, primary), days in sorted(groups.items()):
        for start, end in _merge_ranges(days, max_gap_days):
            requests.append((role, location, primary, start, end))
    return requests


def scan_report_requirements(paths):
    """
    扫描多个报告，汇总需要的日期及其角色。
    返回 {日期: {"target"/"similar"}}，重复日期自动合并。
    """
    requirements = {}
    for path in paths:
        try:
            _, _, data = load_report(path)
        except Exception:  # noqa: BLE001
            continue
        target, similar = report_dates(data)
        requirements.setdefault(target, set()).add("target")
        for day in similar:
            requirements.setdefault(day, set()).add("similar")
    return requirements


def plan_missing(conn, requirements):
    """
    对照数据库，统计已有 / 缺失。
    返回 (missing, present_count)，missing 元素为 (日期, 角色, 站点)。
    """
    missing, present = [], 0
    for day in sorted(requirements):
        for role in ROLE_ORDER:
            if role not in requirements[day]:
                continue
            for location in LOCATIONS:
                if any(
                    get_series(conn, day, location, src, "temp") is not None
                    for src in SOURCE_PRIORITY[role]
                ):
                    present += 1
                else:
                    missing.append((day, role, location))
    return missing, present


def prefetch(conn, missing, quiet=False, max_gap_days=MAX_GAP_DAYS):
    """
    按缺失清单抓取：同角色/站点/数据源的日期先合并成区间，一次请求覆盖多天。
    返回 (写入条数, 失败列表, 实际请求次数)。
    """
    fetched, failed, calls = 0, [], 0
    for role, location, primary, start, end in group_requests(missing, max_gap_days):
        span = start if start == end else f"{start}~{end}"
        order = [primary] + [s for s in SOURCE_PRIORITY[role] if s != primary]
        for src in order:
            calls += 1
            try:
                count = fetch_weather(conn, location, start, end, src)
                fetched += count
                if not quiet:
                    print(f"    补数 {span} {location} <- {src}：{count} 条")
                break
            except Exception as exc:  # noqa: BLE001
                if not quiet:
                    print(f"    补数 {span} {location} <- {src} 失败：{exc}")
        else:
            failed.append(f"{span} {location}({role})")
    return fetched, failed, calls


def prepare_reports(paths, db_path=None, quiet=False):
    """
    批量处理前的统一准备：扫描所有报告 → 合并去重需求 → 只补抓缺失的
    （同一数据源的多天合并成区间，一次请求覆盖多天）。
    返回统计 dict。
    """
    conn = open_db(db_path)
    requirements = scan_report_requirements(paths)
    missing, present = plan_missing(conn, requirements)
    planned_calls = len(group_requests(missing))
    fetched, failed, calls = prefetch(conn, missing, quiet=quiet)
    conn.close()
    return {
        "reports": len(paths),
        "unique_dates": len(requirements),
        "required": present + len(missing),
        "present": present,
        "missing": len(missing),
        "planned_calls": planned_calls,
        "calls": calls,
        "fetched": fetched,
        "failed": failed,
    }


def inject_report(conn, report_path, target_source=None, similar_source=None):
    """用库中数据回写报告，返回 (改动列表, 缺失列表)。"""
    text, match, data = load_report(report_path)
    target, similar = report_dates(data)
    changed, missing = [], []

    # 申报日：weather_w / weather_g（对象形式，逐要素）
    for field, location in REPORT_FIELDS.items():
        for variable in VARIABLE_ORDER:
            series = pick_series(conn, target, location, "target", variable, target_source)
            if series is None:
                missing.append(f"{target} {location}.{variable}")
                continue
            data[field][variable] = series
            changed.append(f"{target} {location}.{variable}")

    # 相似日：weather_w / weather_g（数组形式，按 VARIABLE_ORDER 顺序）
    for day_data in data.get("similar_days", []):
        day = day_data["date"]
        for field, location in REPORT_FIELDS.items():
            series_list = [
                pick_series(conn, day, location, "similar", variable, similar_source)
                for variable in VARIABLE_ORDER
            ]
            if all(s is None for s in series_list):
                missing.append(f"{day} {location}")
                continue
            current = day_data[field]
            for idx, series in enumerate(series_list):
                if series is None:
                    continue
                while len(current) <= idx:
                    current.append([])
                current[idx] = series
            changed.append(f"{day} {location}")

    if not changed:
        return changed, missing

    new_json = json.dumps(data, ensure_ascii=False, indent=2)
    write_text(report_path, text[: match.start(2)] + new_json + text[match.end(2) :])
    return changed, missing


def inject_only(report_path, db_path=None):
    """只回写（数据已在 prepare 阶段补齐），不联网。"""
    conn = open_db(db_path)
    changed, missing = inject_report(conn, report_path)
    conn.close()
    return {"applied": len(changed), "missing": len(missing), "fetched": 0}


def update_report_data(report_path, db_path=None, ensure=True, quiet=False):
    """
    一站式：确保报告涉及的日期数据已入库（缺失即抓取），再回写报告。
    返回 dict(applied=改动数, missing=缺失数, fetched=抓取条数)。
    """
    conn = open_db(db_path)
    text, match, data = load_report(report_path)
    target, similar = report_dates(data)

    fetched = 0
    if ensure:
        jobs = [(target, "target")] + [(d, "similar") for d in similar]
        for day, role in jobs:
            for location in LOCATIONS:
                try:
                    src, count = ensure_day(conn, day, location, role)
                    fetched += count
                    if count and not quiet:
                        print(f"    补数 {day} {location} <- {src}：{count} 条")
                except Exception as exc:  # noqa: BLE001
                    if not quiet:
                        print(f"    补数 {day} {location} 失败：{exc}")

    changed, missing = inject_report(conn, report_path)
    conn.close()
    return {"applied": len(changed), "missing": len(missing), "fetched": fetched}


# ─────────────────────────────────────────────────────────────
# 子命令
# ─────────────────────────────────────────────────────────────


def cmd_init(args):
    conn = open_db(args.db)
    conn.close()
    print(f"已创建/校验数据库：{args.db or DEFAULT_DB}")
    print("  站点：")
    for name, loc in LOCATIONS.items():
        print(f"    {name}  {loc['lat']}N, {loc['lon']}E")
    print(f"  要素：{', '.join(VARIABLE_ORDER)}")
    return 0


def cmd_fetch(args):
    conn = open_db(args.db)

    if args.report:
        _, _, data = load_report(args.report)
        target, similar = report_dates(data)
        jobs = [(target, "target", "申报日")] + [(d, "similar", "相似日") for d in similar]
    elif args.start and args.end:
        jobs = [(args.start, "target", "区间")]
        if args.start != args.end:
            jobs = [(f"{args.start}~{args.end}", "target", "区间")]
    else:
        raise SystemExit("请提供 --report，或 --start 与 --end")

    total = 0
    for day, role, label in jobs:
        for location in LOCATIONS:
            try:
                if "~" in day:
                    start, _, end = day.partition("~")
                    sources = [args.source] if args.source else SOURCE_PRIORITY[role]
                    errs = []
                    for src in sources:
                        try:
                            count = fetch_weather(conn, location, start, end, src)
                            total += count
                            print(f"  [{label}] {start}~{end} {location} <- {src}：{count} 条")
                            break
                        except Exception as exc:  # noqa: BLE001
                            errs.append(f"{src}: {exc}")
                    else:
                        print(f"  [{label}] {start}~{end} {location}：失败（{' | '.join(errs)}）")
                else:
                    src, count = ensure_day(conn, day, location, role, force=bool(args.source))
                    total += count
                    tip = "（已存在，跳过）" if count == 0 else f"{count} 条"
                    print(f"  [{label}] {day} {location} <- {src}：{tip}")
            except Exception as exc:  # noqa: BLE001
                print(f"  [{label}] {day} {location}：失败（{exc}）")
    conn.close()
    print(f"完成，共写入 {total} 条记录。")
    return 0


def cmd_show(args):
    conn = open_db(args.db)

    # 明细模式
    if args.date and args.location:
        where = ["date = ?", "location = ?"]
        params = [args.date, args.location]
        if args.source:
            where.append("source = ?")
            params.append(args.source)
        cols = ", ".join(VARIABLE_ORDER)
        rows = conn.execute(
            f"SELECT source, hour, {cols} FROM weather_hourly WHERE {' AND '.join(where)} "
            "ORDER BY source, hour",
            params,
        ).fetchall()
        if not rows:
            print("（无记录）")
        else:
            print(f"{'数据源':<14}{'时刻':<8}" + "".join(f"{v:<10}" for v in VARIABLE_ORDER))
            for row in rows:
                values = "".join(
                    f"{(('%.2f' % v) if isinstance(v, (int, float)) else '-'):<10}" for v in row[2:]
                )
                print(f"{row[0]:<14}{row[1]:02d}:00   {values}")
        conn.close()
        return 0

    # 概览模式
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
    agg = ", ".join(f"ROUND(AVG({v}), 2)" for v in VARIABLE_ORDER)
    sql = f"SELECT date, location, source, COUNT(*), {agg} FROM weather_hourly"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY date, location, source ORDER BY date, location, source"
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("（无记录）")
    else:
        print(
            f"{'日期':<12}{'站点':<8}{'数据源':<14}{'小时':<6}"
            + "".join(f"{v:<9}" for v in VARIABLE_ORDER)
            + "  <- 各要素均值"
        )
        for row in rows:
            avgs = "".join(
                f"{(('%.2f' % v) if isinstance(v, (int, float)) else '-'):<9}" for v in row[4:]
            )
            print(f"{row[0]:<12}{row[1]:<8}{row[2]:<14}{row[3]:<6}{avgs}")
    conn.close()
    return 0


def cmd_plan(args):
    """只做规划，不抓取：扫描报告并统计有多少日期需要补。"""
    folder = Path(args.dir).resolve() if args.dir else BASE_DIR
    paths = sorted(folder.glob(args.pattern))
    if not paths:
        print(f"目录 {folder} 下未找到 {args.pattern}", file=sys.stderr)
        return 1

    conn = open_db(args.db)
    requirements = scan_report_requirements(paths)
    missing, present = plan_missing(conn, requirements)
    conn.close()

    requests = group_requests(missing)
    print(f"扫描目录：{folder}")
    print(f"报告数量：{len(paths)} 个")
    print(f"唯一日期：{len(requirements)} 个（已合并各报告的重复日期）")
    print(f"日期×角色×站点 组合：{present + len(missing)} 个")
    print(f"  已有数据：{present} 个，无需调用 API")
    print(f"  需要补抓：{len(missing)} 个")
    print(f"  合并为  ：{len(requests)} 个日期区间  ← 预计 API 调用 {len(requests)} 次")

    if args.detail and requests:
        print("\n补抓区间明细：")
        for role, location, primary, start, end in requests:
            role_cn = "申报日" if role == "target" else "相似日"
            span = start if start == end else f"{start} ~ {end}"
            print(f"  {span}  {role_cn}  {location}  <- {primary}")
    return 0


def cmd_sync(args):
    """一站式：先统一规划补数，再逐份回写。"""
    paths = [Path(p) for p in args.reports]
    if not args.no_fetch:
        plan = prepare_reports(paths, args.db, quiet=False)
        print(
            f"规划：报告 {plan['reports']} 个 → 唯一日期 {plan['unique_dates']} 个；"
            f"已有 {plan['present']} 项，需补抓 {plan['missing']} 项，"
            f"实际请求 {plan['calls']} 次（写入 {plan['fetched']} 条）"
        )
        if plan["failed"]:
            print(f"补抓失败 {len(plan['failed'])} 项：{', '.join(plan['failed'][:5])}")
    for report in args.reports:
        result = inject_only(report, args.db)
        print(f"  {report}：回写 {result['applied']} 处，缺失 {result['missing']} 处")
    return 0


def cmd_inject(args):
    if args.ensure:
        result = update_report_data(args.report, args.db, ensure=True)
        print(
            f"已回写 {result['applied']} 处，补抓 {result['fetched']} 条"
            f"，缺失 {result['missing']} 处"
        )
        return 0

    conn = open_db(args.db)
    changed, missing = inject_report(
        conn, args.report, args.target_source, args.similar_source
    )
    conn.close()
    if not changed:
        print("没有可回写的数据，文件未改动。")
    else:
        print(f"已回写 {len(changed)} 处：{', '.join(changed[:6])}"
              + (" ..." if len(changed) > 6 else ""))
    if missing:
        print(f"（{len(missing)} 处无数据已跳过：{', '.join(missing[:6])}"
              + (" ..." if len(missing) > 6 else "") + "）")
    return 0


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(
        description="关岭/贵阳逐小时天气数据管道（Open-Meteo → SQLite → 报告）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--db", default=None, help=f"SQLite 文件路径（默认 {DEFAULT_DB.name}）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="创建本地数据库")

    p_fetch = sub.add_parser("fetch", help="从 Open-Meteo 抓取全要素数据并入库")
    p_fetch.add_argument("--report", help="按报告里的申报日/相似日抓取")
    p_fetch.add_argument("--start", help="起始日期 YYYY-MM-DD")
    p_fetch.add_argument("--end", help="结束日期 YYYY-MM-DD")
    p_fetch.add_argument("--source", choices=list(ENDPOINTS), help="强制指定数据源")

    p_show = sub.add_parser("show", help="查看库中数据")
    p_show.add_argument("--date")
    p_show.add_argument("--location", choices=list(LOCATIONS))
    p_show.add_argument("--source", choices=list(ENDPOINTS))

    p_inject = sub.add_parser("inject", help="用库中数据回写报告")
    p_inject.add_argument("--report", required=True)
    p_inject.add_argument("--ensure", action="store_true", help="先自动补抓缺失数据再回写")
    p_inject.add_argument("--target-source", default=None, choices=list(ENDPOINTS),
                          help="强制申报日数据源（默认按优先级自动选择）")
    p_inject.add_argument("--similar-source", default=None, choices=list(ENDPOINTS),
                          help="强制相似日数据源（默认按优先级自动选择）")

    p_sync = sub.add_parser("sync", help="补数 + 回写（可一次处理多个报告）")
    p_sync.add_argument("reports", nargs="+")
    p_sync.add_argument("--no-fetch", action="store_true", help="只用库中已有数据，不联网补抓")

    p_plan = sub.add_parser("plan", help="只做规划：统计有多少日期需要补抓（不联网）")
    p_plan.add_argument("--dir", help="报告所在文件夹（默认脚本所在文件夹）")
    p_plan.add_argument("--pattern", default="report_*.html", help="文件名通配（默认 report_*.html）")
    p_plan.add_argument("--detail", action="store_true", help="列出每条待补抓明细")

    args = ap.parse_args()
    handlers = {
        "init": cmd_init,
        "fetch": cmd_fetch,
        "show": cmd_show,
        "inject": cmd_inject,
        "sync": cmd_sync,
        "plan": cmd_plan,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
