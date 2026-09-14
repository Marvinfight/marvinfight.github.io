#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
贵州电力套利分析报告 —— 定制转换脚本

把「原始生成」的 report_YYYY-MM-DD.html 转换成当前定制版本。

转换内容（按顺序）：
  1. 删除概览统计中的「当前客户数」卡片
  2. 地名「威宁县 / 威宁」统一改名为「关岭」
  3. 隐藏「综合评分计算公式」卡片
  4. 概览统计中的「基准负荷总量 / 申报电量总量 / 预期平均价差」替换为「装机容量 80 MW」
  5. 隐藏「相似日 历史负荷曲线」卡片
  6. 删除「申报曲线 vs 基准负荷」卡片及其图表脚本，并让「净方向概率 & 投机头寸」占满整行
  7. 逐小时套利明细删除「基准负荷 / 加权价差 / 投机头寸 / 申报电量」四列
  8. 隐藏套利方案下的「申报逻辑」说明
  9. 隐藏顶栏的「生成时间」
  10. 配色主题：深色 → 浅色（白色背景）

（兼容两套历史模板：早期文件的套利卡片与明细表列名不同，脚本会自动识别。）

用法：
  # 【推荐】批量转换脚本所在文件夹下的所有 report_*.html（原地覆盖）
  python convert_report.py

  # 只预览效果，不写入文件
  python convert_report.py --dry-run

  # 指定要批量转换的文件夹（原地覆盖）
  python convert_report.py --dir <folder>

  # 批量转换但保留原文件，输出 report_xxx_converted.html
  python convert_report.py --copy

  # 单个文件，输出到同目录 report_xxx_converted.html
  python convert_report.py report_2026-09-14.html

  # 单个文件，指定输出路径 / 直接覆盖
  python convert_report.py report_2026-09-14.html -o out.html
  python convert_report.py report_2026-09-14.html --in-place
"""

import argparse
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────────────────────


def _t(*lines):
    """把多行拼成以 \\n 分隔的文本（保留每行自带缩进）。"""
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# 转换规则
# ─────────────────────────────────────────────────────────────

# 规则 2：地名改名（先长后短，避免重复替换）
RENAMES = [
    ("威宁县", "关岭"),
    ("威宁", "关岭"),
]

# 其余规则：(说明, 原始片段, 替换片段)
REPLACEMENTS = [
    # 规则 1：删除「当前客户数」统计卡片
    (
        "删除概览中的「当前客户数」",
        _t(
            """    { lbl:'当前客户数', val: `${tc.cust_count} 个`, cls: D.any_cust_mismatch ? 'negative' : 'positive' },""",
            "",
        ),
        "",
    ),
    # 规则 3：隐藏「综合评分计算公式」卡片
    (
        "隐藏「综合评分计算公式」卡片",
        _t(
            """  <!-- 评分公式说明 -->""",
            """  <div class="card" style="margin-bottom:16px;background:rgba(100,255,218,0.04);border-color:rgba(100,255,218,0.2)">""",
        ),
        _t(
            """  <!-- 评分公式说明（已隐藏） -->""",
            """  <div class="card" style="display:none;margin-bottom:16px;background:rgba(100,255,218,0.04);border-color:rgba(100,255,218,0.2)">""",
        ),
    ),
    # 规则 4：概览统计三项 -> 装机容量 80 MW
    (
        "概览统计替换为「装机容量 80 MW」",
        _t(
            """    { lbl:'基准负荷总量', val: base.toFixed(2)+' MWh' + (D.any_cust_mismatch ? ' <small style="color:#ffd166">已缩放</small>' : ''), raw: D.any_cust_mismatch, cls:'neutral' },""",
            """    { lbl:'申报电量总量', val: decl.toFixed(2)+' MWh', cls: decl>base?'positive':'negative' },""",
            """    { lbl:'预期平均价差', val: wSpr.toFixed(1)+' ¥/MWh', cls: wSpr>0?'positive':'negative' },""",
            "",
        ),
        _t(
            """    { lbl:'装机容量', val: '80 MW', cls:'neutral' },""",
            "",
        ),
    ),
    # 规则 4（续）：清理因此失效的变量声明
    (
        "清理概览统计中失效的变量声明",
        _t(
            """  const arb   = D.arbitrage;""",
            """  const base  = arb.base.reduce((s,v)=>s+v,0);""",
            """  const decl  = arb.declared.reduce((s,v)=>s+v,0);""",
            """  const maxPos= Math.max(...arb.pos.map(Math.abs));""",
            """  const wSpr  = arb.spread.reduce((s,v)=>s+v,0)/24;""",
            """  const tc    = D.target_calendar;""",
        ),
        _t(
            """  const tc    = D.target_calendar;""",
        ),
    ),
    # 规则 5：隐藏「相似日 历史负荷曲线」卡片
    (
        "隐藏「相似日 历史负荷曲线」卡片",
        _t(
            """    <div class="card">""",
            """      <div class="card-title"><div class="dot" style="background:#a8dadc"></div>相似日 历史负荷曲线</div>""",
            """      <canvas id="chart-sim-load"></canvas>""",
            """    </div>""",
        ),
        _t(
            """    <!-- 相似日 历史负荷曲线（已隐藏） -->""",
            """    <div class="card" style="display:none">""",
            """      <div class="card-title"><div class="dot" style="background:#a8dadc"></div>相似日 历史负荷曲线</div>""",
            """      <canvas id="chart-sim-load"></canvas>""",
            """    </div>""",
        ),
    ),
    # 规则 6：删除「申报曲线 vs 基准负荷」卡片，并让剩下的卡片占满整行
    (
        "删除「申报曲线 vs 基准负荷」卡片",
        _t(
            """  <div class="grid-2">""",
            """    <div class="card">""",
            """      <div class="card-title"><div class="dot"></div>申报曲线 vs 基准负荷</div>""",
            """      <canvas id="chart-arb-load"></canvas>""",
            """    </div>""",
            """    <div class="card">""",
            """      <div class="card-title"><div class="dot" style="background:#ffd166"></div>净方向概率 & 投机头寸</div>""",
            """      <canvas id="chart-arb-pos"></canvas>""",
            """    </div>""",
            """  </div>""",
        ),
        _t(
            """  <div class="card">""",
            """    <div class="card-title"><div class="dot" style="background:#ffd166"></div>净方向概率 & 投机头寸</div>""",
            """    <canvas id="chart-arb-pos"></canvas>""",
            """  </div>""",
        ),
    ),
    # 规则 6（旧模板）：卡片标题为「加权预期价差 & 套利头寸」
    (
        "[旧模板] 删除「申报曲线 vs 基准负荷」卡片",
        _t(
            """  <div class="grid-2">""",
            """    <div class="card">""",
            """      <div class="card-title"><div class="dot"></div>申报曲线 vs 基准负荷</div>""",
            """      <canvas id="chart-arb-load"></canvas>""",
            """    </div>""",
            """    <div class="card">""",
            """      <div class="card-title"><div class="dot" style="background:#ffd166"></div>加权预期价差 & 套利头寸</div>""",
            """      <canvas id="chart-arb-pos"></canvas>""",
            """    </div>""",
            """  </div>""",
        ),
        _t(
            """  <div class="card">""",
            """    <div class="card-title"><div class="dot" style="background:#ffd166"></div>加权预期价差 & 套利头寸</div>""",
            """    <canvas id="chart-arb-pos"></canvas>""",
            """  </div>""",
        ),
    ),
    # 规则 6（续）：删除失效的 chart-arb-load 图表脚本
    (
        "删除 chart-arb-load 图表脚本",
        _t(
            """const arb = D.arbitrage;""",
            """mkChart('chart-arb-load', {""",
            """  type:'line', data:{""",
            """    labels: HL,""",
            """    datasets:[""",
            """      { label:'基准负荷', data:arb.base, borderColor:'#8892b0', backgroundColor:'rgba(136,146,176,0.1)', fill:true, tension:0.4, borderWidth:2, pointRadius:0 },""",
            """      { label:'申报电量', data:arb.declared, borderColor:'#64ffda', backgroundColor:'rgba(100,255,218,0.15)', fill:true, tension:0.4, borderWidth:2.5, pointRadius:0 },""",
            """    ]""",
            """  },""",
            """  options: opts({ scales:{ y:{ title:{ display:true, text:'电量(MWh)', color:'#8892b0' } } } })""",
            """});""",
            """""",
            """mkChart('chart-arb-pos', {""",
        ),
        _t(
            """const arb = D.arbitrage;""",
            """mkChart('chart-arb-pos', {""",
        ),
    ),
    # 规则 7：逐小时套利明细 —— 表头与循环变量
    (
        "逐小时明细：精简表头与循环变量",
        _t(
            """  const thead = `<thead><tr>""",
            """    <th>时段</th><th>基准负荷(MWh)</th><th>加权价差(¥/MWh)</th>""",
            """    <th>看多概率</th><th>看空概率</th><th>净方向概率</th>""",
            """    <th>投机头寸(MWh)</th><th>头寸比例</th><th>申报电量(MWh)</th>""",
            """  </tr></thead>`;""",
            """  let tbody = '<tbody>';""",
            """  for (let h=0; h<24; h++) {""",
            """    const pos  = arb.pos[h], pct = arb.pct[h], spr = arb.spread[h];""",
            """    const pl   = arb.prob_long[h], ps = arb.prob_short[h], np = arb.net_prob[h];""",
            """    const pCls = pos > 0 ? 'positive' : pos < 0 ? 'negative' : '';""",
            """    const sCls = spr > 0 ? 'negative' : spr < 0 ? 'positive' : '';""",
            """    const npCls = np > 0 ? 'positive' : np < 0 ? 'negative' : '';""",
        ),
        _t(
            """  const thead = `<thead><tr>""",
            """    <th>时段</th><th>看多概率</th><th>看空概率</th><th>净方向概率</th><th>头寸比例</th>""",
            """  </tr></thead>`;""",
            """  let tbody = '<tbody>';""",
            """  for (let h=0; h<24; h++) {""",
            """    const pct  = arb.pct[h];""",
            """    const pl   = arb.prob_long[h], ps = arb.prob_short[h], np = arb.net_prob[h];""",
            """    const npCls = np > 0 ? 'positive' : np < 0 ? 'negative' : '';""",
        ),
    ),
    # 规则 7（续）：逐小时套利明细 —— 表格行
    (
        "逐小时明细：精简数据行",
        _t(
            """    tbody += `<tr>""",
            """      <td>${HL[h]}</td>""",
            """      <td>${arb.base[h].toFixed(3)}</td>""",
            """      <td class="${sCls}">${spr.toFixed(2)}</td>""",
            """      <td class="positive">${(pl*100).toFixed(1)}%</td>""",
            """      <td class="negative">${(ps*100).toFixed(1)}%</td>""",
            """      <td>${npBar}</td>""",
            """      <td class="${pCls}">${pos >= 0 ? '+' : ''}${pos.toFixed(3)}</td>""",
            """      <td>${pill}</td>""",
            """      <td><strong>${arb.declared[h].toFixed(3)}</strong></td>""",
            """    </tr>`;""",
        ),
        _t(
            """    tbody += `<tr>""",
            """      <td>${HL[h]}</td>""",
            """      <td class="positive">${(pl*100).toFixed(1)}%</td>""",
            """      <td class="negative">${(ps*100).toFixed(1)}%</td>""",
            """      <td>${npBar}</td>""",
            """      <td>${pill}</td>""",
            """    </tr>`;""",
        ),
    ),
    # 规则 7（旧模板）：明细表为「套利头寸」，且无看多/看空/净方向概率列
    (
        "[旧模板] 逐小时明细：精简表头与循环变量",
        _t(
            """  const thead = `<thead><tr>""",
            """    <th>时段</th><th>基准负荷(MWh)</th><th>加权价差(¥/MWh)</th>""",
            """    <th>套利头寸(MWh)</th><th>头寸比例</th><th>申报电量(MWh)</th>""",
            """  </tr></thead>`;""",
            """  let tbody = '<tbody>';""",
            """  for (let h=0; h<24; h++) {""",
            """    const pos  = arb.pos[h], pct = arb.pct[h], spr = arb.spread[h];""",
            """    const pCls = pos > 0 ? 'positive' : pos < 0 ? 'negative' : '';""",
            """    const sCls = spr > 0 ? 'negative' : spr < 0 ? 'positive' : '';""",
        ),
        _t(
            """  const thead = `<thead><tr>""",
            """    <th>时段</th><th>头寸比例</th>""",
            """  </tr></thead>`;""",
            """  let tbody = '<tbody>';""",
            """  for (let h=0; h<24; h++) {""",
            """    const pct  = arb.pct[h];""",
        ),
    ),
    (
        "[旧模板] 逐小时明细：精简数据行",
        _t(
            """    tbody += `<tr>""",
            """      <td>${HL[h]}</td>""",
            """      <td>${arb.base[h].toFixed(3)}</td>""",
            """      <td class="${sCls}">${spr.toFixed(2)}</td>""",
            """      <td class="${pCls}">${pos >= 0 ? '+' : ''}${pos.toFixed(3)}</td>""",
            """      <td>${pill}</td>""",
            """      <td><strong>${arb.declared[h].toFixed(3)}</strong></td>""",
            """    </tr>`;""",
        ),
        _t(
            """    tbody += `<tr>""",
            """      <td>${HL[h]}</td>""",
            """      <td>${pill}</td>""",
            """    </tr>`;""",
        ),
    ),
    # 规则 8：隐藏「申报逻辑」说明段落
    (
        "隐藏套利方案下的「申报逻辑」说明",
        _t(
            """  <p style="color:var(--muted);font-size:12px;margin-bottom:14px">""",
            """    申报逻辑：""",
        ),
        _t(
            """  <p style="display:none;color:var(--muted);font-size:12px;margin-bottom:14px">""",
            """    申报逻辑：""",
        ),
    ),
    # 规则 9：隐藏顶栏的「生成时间」
    (
        "隐藏顶栏的「生成时间」",
        _t(
            """    <span style="color:var(--muted);font-size:12px">生成时间 <strong id="gentime"></strong></span>""",
        ),
        _t(
            """    <span style="display:none;color:var(--muted);font-size:12px">生成时间 <strong id="gentime"></strong></span>""",
        ),
    ),
]


# ─────────────────────────────────────────────────────────────
# 浅色主题：全局颜色替换
# 说明：深色主题所有颜色都是字面量，这里统一换成浅色主题配色。
#       因为结构规则里也引用了这些颜色，主题替换必须放在结构规则之后执行。
# ─────────────────────────────────────────────────────────────
THEME_REPLACEMENTS = [
    ("页面背景 --bg", "#0f1117", "#f5f7fa"),
    ("卡片背景 --card", "#1a1d27", "#ffffff"),
    ("边框/网格 --border", "#2d3148", "#e5e7eb"),
    ("正文颜色 --text", "#e2e8f0", "#1f2733"),
    ("次要文字 --muted", "#8892b0", "#6b7280"),
    ("强调色 --accent/--green", "#64ffda", "#0d9488"),
    ("强调黄 --yellow", "#ffd166", "#d97706"),
    ("强调蓝 --blue", "#8ecae6", "#0284c7"),
    ("强调红 --red", "#ff6b6b", "#dc2626"),
    ("浅蓝点缀", "#a8dadc", "#64748b"),
    ("白色蒙层 -> 黑色蒙层", "rgba(255,255,255,", "rgba(0,0,0,"),
    ("图例提示文字", "color:#556;", "color:#9ca3af;"),
]


# ─────────────────────────────────────────────────────────────
# 转换逻辑
# ─────────────────────────────────────────────────────────────


def convert(html, nl):
    """对 html 文本执行全部转换，返回 (新文本, 日志列表)。"""
    log = []

    # 规则 2：地名改名
    for old, new in RENAMES:
        cnt = html.count(old)
        if cnt:
            html = html.replace(old, new)
            log.append((f"地名改名 {old} -> {new}", f"替换 {cnt} 处"))
        else:
            log.append((f"地名改名 {old} -> {new}", "未找到（可能已处理）"))

    # 其余规则
    for name, old, new in REPLACEMENTS:
        old = old.replace("\n", nl)
        new = new.replace("\n", nl)
        cnt = html.count(old)

        if cnt == 1:
            html = html.replace(old, new)
            log.append((name, "已应用"))
        elif cnt == 0:
            if new and new in html:
                log.append((name, "跳过（已是定制版）"))
            else:
                log.append((name, "未找到匹配，跳过"))
        else:
            raise RuntimeError(f"片段匹配到 {cnt} 处（应为 1 处），请检查模板：{name}")

    # 最后执行浅色主题替换（放在结构规则之后，避免影响结构规则的匹配）
    for name, old, new in THEME_REPLACEMENTS:
        cnt = html.count(old)
        if cnt:
            html = html.replace(old, new)
            log.append((f"配色 {name}", f"替换 {cnt} 处"))
        else:
            log.append((f"配色 {name}", "无匹配（可能已处理）"))

    return html, log


def check_residual(html):
    """返回仍残留的、本应被处理掉的标记。"""
    residual = []
    for token in ("威宁县", "当前客户数"):
        if token in html:
            residual.append(token)
    return residual


def convert_file(src: Path, dst: Path, write=True, verbose=False):
    """转换单个文件，返回统计信息。"""
    with open(src, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    nl = "\r\n" if "\r\n" in raw else "\n"

    html, log = convert(raw, nl)
    applied = sum(1 for _, s in log if "已应用" in s or "替换" in s)
    skipped = len(log) - applied
    residual = check_residual(html)

    if write:
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(html)

    if verbose:
        print(f"\n=== {src.name} -> {dst.name} ===")
        for name, status in log:
            print(f"  [{'OK ' if ('已应用' in status or '替换' in status) else '-- '}] {name}: {status}")
        if residual:
            print(f"  [!] 注意：仍残留 {', '.join(residual)}")
        else:
            print("  [OK ] 校验通过：无残留标记")
    else:
        tag = "转换" if applied else "跳过"
        warn = f"  [!] 残留 {','.join(residual)}" if residual else ""
        print(f"  [{tag}] {src.name}  (改动 {applied}/{len(log)} 条){warn}")

    return {"applied": applied, "skipped": skipped, "residual": residual}


def main():
    ap = argparse.ArgumentParser(
        description="把原始贵州电力套利报告 HTML 转换为定制版本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("inputs", nargs="*", help="待转换的 HTML 文件（留空则批量转换脚本所在文件夹）")
    ap.add_argument("-o", "--output", help="输出文件（仅单个输入时可用）")
    ap.add_argument("--dir", help="批量转换该文件夹（默认：脚本所在文件夹）")
    ap.add_argument("--in-place", action="store_true", help="单文件模式：直接覆盖原文件")
    ap.add_argument("--copy", action="store_true", help="批量模式：输出 report_xxx_converted.html，不覆盖原文件")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写入文件")
    args = ap.parse_args()

    # ── 批量模式：未指定具体文件 ──
    if not args.inputs:
        folder = Path(args.dir).resolve() if args.dir else Path(__file__).resolve().parent
        targets = sorted(folder.glob("report_*.html"))
        if not targets:
            print(f"目录 {folder} 下未找到 report_*.html", file=sys.stderr)
            return 1

        print(f"批量转换 {len(targets)} 个文件（目录：{folder}）"
              + ("  [预览模式，不写入]" if args.dry_run else ""))
        changed = 0
        for src in targets:
            dst = src.with_name(src.stem + "_converted.html") if args.copy else src
            res = convert_file(src, dst, write=not args.dry_run, verbose=False)
            if res["applied"]:
                changed += 1
        print(f"\n完成：共 {len(targets)} 个文件，其中 {changed} 个发生了改动。")
        return 0

    # ── 单文件模式 ──
    if args.output and len(args.inputs) > 1:
        print("使用 -o 时只能指定一个输入文件", file=sys.stderr)
        return 1

    for item in args.inputs:
        src = Path(item)
        if not src.is_file():
            print(f"文件不存在：{src}", file=sys.stderr)
            return 1
        if args.output:
            dst = Path(args.output)
        elif args.in_place:
            dst = src
        else:
            dst = src.with_name(src.stem + "_converted.html")
        convert_file(src, dst, write=not args.dry_run, verbose=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
