#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成 guizhou/index.html 日历入口页，并给各报告页加「前一天 / 日历 / 后一天」导航。

- 入口页：月历网格（周一起始），有报告的日期高亮可点，点击进入 report_YYYY-MM-DD.html
- 报告页：底部悬浮一条导航（幂等刷新，不会重复插入）
- 纯静态、无外部依赖，可以直接放在 GitHub Pages 上用

用法：
    python make_index.py               # 重建 index.html 并刷新所有报告的导航
    python make_index.py --no-nav       # 只重建 index.html
    python make_index.py --dir <folder> # 指定报告所在文件夹
"""

import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPORT_RE = re.compile(r"^report_(\d{4})\D(\d{1,2})\D(\d{1,2})\.html$", re.I)
NAV_RE = re.compile(r"<!-- date-nav-start -->.*?<!-- date-nav-end -->", re.S)
NAV_MARKER = "<!-- date-nav-start -->"


# ─────────────────────────────────────────────────────────────
# 公共
# ─────────────────────────────────────────────────────────────


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def scan_reports(folder):
    """返回排序后的日期列表 ['2026-03-04', ...]"""
    days = []
    for path in folder.glob("report_*.html"):
        match = REPORT_RE.match(path.name)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups())
        days.append(f"{year:04d}-{month:02d}-{day:02d}")
    return sorted(set(days))


# ─────────────────────────────────────────────────────────────
# 入口页
# ─────────────────────────────────────────────────────────────

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>贵州电力套利分析 · 报告日历</title>
<style>
  :root {
    --bg: #f5f7fa; --card: #ffffff; --border: #e5e7eb;
    --text: #1f2733; --muted: #6b7280; --accent: #0d9488;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font-family: 'Segoe UI', -apple-system, 'Microsoft YaHei', sans-serif;
    font-size: 14px; line-height: 1.6; padding: 28px 16px 48px;
  }
  .wrap { max-width: 760px; margin: 0 auto; }
  header { margin-bottom: 18px; }
  h1 { font-size: 20px; font-weight: 700; letter-spacing: .5px; }
  h1 span { color: var(--accent); }
  .sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
  .card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 18px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,.04);
  }
  .cal-head {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 12px;
  }
  .cal-head button {
    width: 32px; height: 32px; border-radius: 8px; cursor: pointer;
    border: 1px solid var(--border); background: #fff; color: var(--text);
    font-size: 15px; line-height: 1;
  }
  .cal-head button:hover { border-color: var(--accent); color: var(--accent); }
  .label { font-size: 15px; font-weight: 600; }
  .weekdays, .grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
  .weekdays { margin-bottom: 6px; }
  .weekdays div {
    text-align: center; font-size: 12px; color: var(--muted); padding: 4px 0;
  }
  .cell {
    aspect-ratio: 1 / 1; border-radius: 8px; display: flex;
    align-items: center; justify-content: center;
    font-size: 13px; border: 1px solid transparent;
  }
  .cell.blank { visibility: hidden; }
  .cell.off { color: #d1d5db; }
  .cell.has {
    cursor: pointer; background: #eef7f5; border-color: #b9e2da;
    color: var(--accent); font-weight: 700;
  }
  .cell.has:hover { background: var(--accent); border-color: var(--accent); color: #fff; }
  .cell.today { outline: 2px solid #d97706; outline-offset: -2px; }
  .quick { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .quick a, .quick button {
    font-size: 12px; padding: 5px 12px; border-radius: 999px; cursor: pointer;
    background: #eef7f5; color: var(--accent); border: 1px solid #b9e2da;
    text-decoration: none;
  }
  .quick a:hover, .quick button:hover { background: var(--accent); color: #fff; }
  .legend { margin-top: 14px; font-size: 12px; color: var(--muted); }
  .legend i {
    display: inline-block; width: 10px; height: 10px; border-radius: 3px;
    background: #eef7f5; border: 1px solid #b9e2da; margin-right: 6px;
    vertical-align: -1px;
  }
  .pick { margin-top: 14px; font-size: 12px; color: var(--muted); }
  .pick input {
    font-family: inherit; font-size: 12px; padding: 5px 8px;
    border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); background: #fff;
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>贵州电力现货套利分析 <span>· 报告日历</span></h1>
    <p class="sub">共 __COUNT__ 份日报 · __FIRST__ ~ __LAST__ · 点击高亮日期查看当日报告</p>
  </header>

  <div class="card">
    <div class="cal-head">
      <button id="prev" title="上个月">‹</button>
      <div class="label" id="label"></div>
      <button id="next" title="下个月">›</button>
    </div>
    <div class="weekdays">
      <div>一</div><div>二</div><div>三</div><div>四</div><div>五</div><div>六</div><div>日</div>
    </div>
    <div class="grid" id="grid"></div>

    <div class="quick">
      <button id="to-latest">最新一期</button>
      <button id="to-first">最早一期</button>
      <span class="pick">或直接选日期：<input type="date" id="picker" min="__FIRST__" max="__LAST__"></span>
    </div>
    <div class="legend"><i></i>高亮日期 = 有报告可查看；灰色日期无报告</div>
  </div>
</div>

<script>
const DATES = __DATES__;
const SET = new Set(DATES);
const FIRST = DATES[0];
const LAST = DATES[DATES.length - 1];

const pad = n => String(n).padStart(2, '0');
const grid = document.getElementById('grid');
const label = document.getElementById('label');

let curYear, curMonth;
{
  const [y, m] = LAST.split('-').map(Number);
  curYear = y; curMonth = m;
}

function isoOf(y, m, d) { return `${y}-${pad(m)}-${pad(d)}`; }

function render() {
  label.textContent = `${curYear} 年 ${curMonth} 月`;
  grid.innerHTML = '';

  // 周一为一周起点：JS getDay() 中 0=周日
  const offset = (new Date(curYear, curMonth - 1, 1).getDay() + 6) % 7;
  const total = new Date(curYear, curMonth, 0).getDate();

  for (let i = 0; i < offset; i++) {
    const b = document.createElement('div');
    b.className = 'cell blank';
    grid.appendChild(b);
  }
  for (let d = 1; d <= total; d++) {
    const iso = isoOf(curYear, curMonth, d);
    const el = document.createElement('div');
    el.textContent = d;
    if (SET.has(iso)) {
      el.className = 'cell has';
      el.title = `${iso} · 查看当日报告`;
      el.onclick = () => { location.href = `report_${iso}.html`; };
    } else {
      el.className = 'cell off';
    }
    grid.appendChild(el);
  }
}

function goMonth(delta) {
  curMonth += delta;
  if (curMonth < 1) { curMonth = 12; curYear--; }
  if (curMonth > 12) { curMonth = 1; curYear++; }
  render();
}

function gotoDate(iso) {
  if (!iso) return;
  const [y, m] = iso.split('-').map(Number);
  curYear = y; curMonth = m;
  render();
}

document.getElementById('prev').onclick = () => goMonth(-1);
document.getElementById('next').onclick = () => goMonth(1);
document.getElementById('to-latest').onclick = () => gotoDate(LAST);
document.getElementById('to-first').onclick = () => gotoDate(FIRST);
document.getElementById('picker').onchange = e => {
  const v = e.target.value;
  if (!v) return;
  gotoDate(v);
  if (SET.has(v)) location.href = `report_${v}.html`;
};

render();
</script>
</body>
</html>
"""


def build_index_html(days):
    dates_json = json.dumps(days, ensure_ascii=False, separators=(",", ":"))
    return (
        INDEX_TEMPLATE.replace("__DATES__", dates_json)
        .replace("__COUNT__", str(len(days)))
        .replace("__FIRST__", days[0] if days else "")
        .replace("__LAST__", days[-1] if days else "")
    )


def write_index(folder, days, filename="index.html"):
    path = folder / filename
    write_text(path, build_index_html(days))
    return path


# ─────────────────────────────────────────────────────────────
# 报告页导航
# ─────────────────────────────────────────────────────────────

NAV_STYLE = (
    "position:fixed;left:50%;transform:translateX(-50%);bottom:16px;z-index:999;"
    "display:flex;gap:6px;align-items:center;white-space:nowrap;"
    "background:rgba(255,255,255,.94);border:1px solid #e5e7eb;border-radius:999px;"
    "padding:6px 10px;box-shadow:0 4px 14px rgba(0,0,0,.08);"
    "font-family:'Segoe UI',-apple-system,'Microsoft YaHei',sans-serif;font-size:12px"
)
NAV_LINK_STYLE = (
    "padding:3px 10px;border-radius:999px;text-decoration:none;"
    "color:#0d9488;background:#eef7f5"
)
NAV_OFF_STYLE = (
    "padding:3px 10px;border-radius:999px;color:#c7ccd4;background:#f6f7f9"
)


def build_nav_block(day, prev_day, next_day):
    def link(target, text):
        if target:
            return f'<a href="report_{target}.html" style="{NAV_LINK_STYLE}">{text}</a>'
        return f'<span style="{NAV_OFF_STYLE}">{text}</span>'

    return (
        f"{NAV_MARKER}\n"
        f'<div id="date-nav" style="{NAV_STYLE}">'
        f'{link(prev_day, "◀ 前一天")}'
        f'<a href="index.html" style="{NAV_LINK_STYLE}">日历</a>'
        f'{link(next_day, "后一天 ▶")}'
        f'<span style="color:#6b7280">{day}</span>'
        f"</div>\n"
        f"<!-- date-nav-end -->"
    )


def inject_nav(folder, days):
    """给每个报告页插入/刷新底部导航，返回实际改动的文件数。"""
    updated = 0
    for index, day in enumerate(days):
        path = folder / f"report_{day}.html"
        if not path.is_file():
            continue
        block = build_nav_block(
            day,
            days[index - 1] if index > 0 else None,
            days[index + 1] if index < len(days) - 1 else None,
        )
        text = read_text(path)

        if NAV_RE.search(text):
            new_text = NAV_RE.sub(lambda _m: block, text, count=1)
        elif "</body>" in text:
            new_text = text.replace("</body>", block + "\n</body>", 1)
        else:
            continue

        if new_text != text:
            write_text(path, new_text)
            updated += 1
    return updated


# ─────────────────────────────────────────────────────────────
# 对外入口
# ─────────────────────────────────────────────────────────────


def refresh(folder, nav=True, verbose=False):
    """重建 index.html（并按需刷新导航），返回统计 dict。"""
    folder = Path(folder)
    days = scan_reports(folder)
    if not days:
        raise SystemExit(f"目录 {folder} 下未找到 report_*.html")
    write_index(folder, days)
    changed = inject_nav(folder, days) if nav else 0
    if verbose:
        print(f"入口页：{folder / 'index.html'}（{len(days)} 天）")
        if nav:
            print(f"导航：已刷新 {changed} 个报告页")
    return {"days": len(days), "nav": changed, "first": days[0], "last": days[-1]}


def main():
    ap = argparse.ArgumentParser(description="生成报告日历入口页，并刷新报告页导航")
    ap.add_argument("--dir", help="报告所在文件夹（默认脚本所在文件夹）")
    ap.add_argument("--no-nav", action="store_true", help="只重建 index.html，不给报告页加导航")
    args = ap.parse_args()

    folder = Path(args.dir).resolve() if args.dir else BASE_DIR
    stats = refresh(folder, nav=not args.no_nav, verbose=True)
    print(f"完成：{stats['first']} ~ {stats['last']}，共 {stats['days']} 天")
    return 0


if __name__ == "__main__":
    sys.exit(main())
