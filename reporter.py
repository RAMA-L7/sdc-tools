"""
SDC Tools — HTML Report Generator
Produces self-contained signoff-quality HTML reports from checker, diff, and
clock-relations results. No external dependencies — all CSS is inline.

Usage:
    from reporter import generate_check_report, generate_diff_report
    html = generate_check_report(check_result, "path/to/file.sdc")
    open("report.html", "w").write(html)
"""

import os
from datetime import date
from typing import Optional

from rules_registry import APP_VERSION, get_rule

# ── Base Template ───────────────────────────────────────────────────────────

_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 1000px; margin: 0 auto; padding: 30px 24px; color: #1f2937;
       background: #ffffff; line-height: 1.5; }
h1 { font-size: 26px; font-weight: 700; margin-bottom: 2px; }
h2 { font-size: 16px; font-weight: 400; color: #6b7280; margin-bottom: 20px; }
h3 { font-size: 15px; font-weight: 600; margin: 20px 0 8px 0; }
.metrics { display: flex; gap: 12px; margin: 16px 0 20px 0; flex-wrap: wrap; }
.metric { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px;
           padding: 14px 22px; min-width: 110px; text-align: center; }
.metric .num { font-size: 30px; font-weight: 700; line-height: 1.1; }
.metric .label { font-size: 11px; color: #6b7280; text-transform: uppercase;
                  letter-spacing: 0.06em; margin-top: 2px; }
.metric.green .num { color: #059669; }
.metric.red .num { color: #dc2626; }
.metric.yellow .num { color: #b8860b; }
.metric.blue .num { color: #2563eb; }
.badge-row { margin: 12px 0 16px 0; }
.badge { display: inline-block; padding: 4px 14px; border-radius: 20px;
          font-size: 13px; font-weight: 600; margin-right: 8px; margin-bottom: 4px; }
.badge-red { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.badge-yellow { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
.badge-blue { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
table { width: 100%; border-collapse: collapse; margin: 8px 0 16px 0;
         font-size: 13px; }
th { text-align: left; padding: 8px 12px; background: #f3f4f6;
      border-bottom: 2px solid #d1d5db; font-weight: 600; white-space: nowrap; }
td { padding: 7px 12px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
tr:hover td { background: #fafafa; }
code { font-family: 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
       font-size: 12px; background: #f3f4f6; padding: 1px 6px; border-radius: 4px;
       word-break: break-all; }
tr.error-row td { background: #fff5f5; }
tr.warn-row td { background: #fffdf0; }
.section { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px 20px;
            margin: 16px 0; }
.section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px;
                  text-transform: uppercase; letter-spacing: 0.04em; color: #374151; }
.empty-state { color: #9ca3af; font-style: italic; padding: 12px 0; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
               gap: 8px; margin: 8px 0; }
.stat-item { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px;
              padding: 8px 12px; display: flex; justify-content: space-between; }
.stat-key { color: #6b7280; font-size: 12px; }
.stat-val { font-weight: 600; font-size: 13px; }
.footer { font-size: 11px; color: #9ca3af; text-align: center; margin-top: 30px;
           border-top: 1px solid #e5e7eb; padding-top: 14px; }
.diff-side { display: grid; grid-template-columns: 1fr 1fr; gap: 0;
             border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
.diff-col { padding: 12px; font-family: 'Fira Code', 'Consolas', monospace;
             font-size: 12px; line-height: 1.6; }
.diff-col-a { background: #fff5f5; }
.diff-col-b { background: #f5fffa; border-left: 1px solid #e5e7eb; }
.diff-added { color: #065f46; background: #d1fae5; padding: 1px 4px; border-radius: 3px; }
.diff-removed { color: #991b1b; background: #fee2e2; padding: 1px 4px; border-radius: 3px; }
.diff-empty { color: #9ca3af; font-style: italic; }
.change-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px 16px;
                margin: 8px 0; }
.change-card.fatal { border-left: 4px solid #dc2626; }
.change-card.warning { border-left: 4px solid #b8860b; }
.change-card.info { border-left: 4px solid #2563eb; }
.change-sev { font-weight: 600; font-size: 11px; text-transform: uppercase;
               letter-spacing: 0.06em; }
.change-sev.fatal { color: #dc2626; }
.change-sev.warning { color: #b8860b; }
.change-sev.info { color: #2563eb; }
.change-rule { font-weight: 600; font-size: 12px; font-family: monospace; }
.change-text { font-family: monospace; font-size: 11px; background: #f3f4f6;
                padding: 4px 8px; border-radius: 4px; margin: 4px 0; display: block;
                white-space: pre-wrap; word-break: break-all; }
.clock-matrix { overflow-x: auto; }
.clock-matrix table { font-size: 12px; }
.clock-matrix td, .clock-matrix th { padding: 6px 10px; text-align: center; white-space: nowrap; }
.matrix-correct { background: #d1fae5; color: #065f46; }
.matrix-mismatch { background: #fee2e2; color: #991b1b; }
.matrix-missing { background: #fef3c7; color: #92400e; }
.matrix-sync-missing { background: #dbeafe; color: #1e40af; }
.legend { display: flex; gap: 16px; margin: 8px 0 16px 0; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 4px; font-size: 12px;
               padding: 2px 8px; border-radius: 4px; }
"""


def _page(title: str, subtitle: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — SDC Tools</title>
<style>{_CSS}</style>
</head>
<body>
<h1>{title}</h1>
<h2>{subtitle}</h2>
{body}
<div class="footer">Generated by <b>SDC Tools</b> v{APP_VERSION} &mdash; {date.today()}</div>
</body></html>"""


def _summary_metrics(items: list[tuple[str, str, str]]) -> str:
    """items: [(value, label, css_class), ...]"""
    parts = []
    for val, label, css in items:
        parts.append(f'<div class="metric {css}"><div class="num">{val}</div><div class="label">{label}</div></div>')
    return f'<div class="metrics">{"".join(parts)}</div>'


def _badge(count: int, label: str, css: str) -> str:
    if count == 0:
        return ""
    return f'<span class="badge badge-{css}">{count} {label}</span>'


def _issue_rows(items, sev_class: str, sev_label: str) -> str:
    rows = ""
    for item in items:
        code = item.code
        msg = item.msg
        rule = get_rule(code)
        tip = f" — {rule.short_name}" if rule else ""
        rows += f"""<tr class="{sev_class}-row">
  <td><code>{code}</code></td>
  <td><span style="font-weight:600">{sev_label}</span></td>
  <td>{msg}</td>
  <td style="color:#6b7280;font-size:11px">{tip}</td>
</tr>\n"""
    return rows


def _table(headers: list[str], rows: str, col_styles: str = "") -> str:
    hdr = "".join(f"<th>{h}</th>" for h in headers)
    return f'<table{col_styles}><thead><tr>{hdr}</tr></thead><tbody>{rows}</tbody></table>'


# ── Check Report ────────────────────────────────────────────────────────────

def generate_check_report(result, filename: str, verbose: bool = False) -> str:
    """Generate a formatted HTML report from a CheckResult."""
    err_c = len(result.errors)
    warn_c = len(result.warnings)
    info_c = len(result.info)
    total = err_c + warn_c + info_c
    stats = result.stats or {}

    metrics = _summary_metrics([
        (str(total), "Total Issues", "blue"),
        (str(err_c), "Errors", "red"),
        (str(warn_c), "Warnings", "yellow"),
        (str(stats.get("clocks", stats.get("Clocks", "—"))), "Clocks", "green"),
    ])

    badges = _badge(err_c, "Errors", "red") + _badge(warn_c, "Warnings", "yellow") + _badge(info_c, "Info", "blue")

    # Issues table
    rows = _issue_rows(result.errors, "error", "ERROR")
    rows += _issue_rows(result.warnings, "warn", "WARNING")
    if verbose:
        rows += _issue_rows(result.info, "info", "INFO")
    issues_table = _table(["Code", "Severity", "Message", "Rule"], rows) if rows else '<div class="empty-state">No issues found.</div>'

    issue_section = f"""<div class="section">
<div class="section-title">Issues</div>
{issues_table}
</div>"""

    # Stats table
    if stats:
        stat_rows = "".join(f'<div class="stat-item"><span class="stat-key">{k}</span><span class="stat-val">{v}</span></div>' for k, v in sorted(stats.items()))
        stats_section = f"""<div class="section">
<div class="section-title">Statistics</div>
<div class="stats-grid">{stat_rows}</div>
</div>"""
    else:
        stats_section = ""

    body = f"""{metrics}
<div class="badge-row">{badges}</div>
{issue_section}
{stats_section}"""

    return _page("SDC Quality Report", os.path.basename(filename), body)


# ── Diff Report ─────────────────────────────────────────────────────────────

def generate_diff_report(result, v1_name: str, v2_name: str) -> str:
    """Generate an HTML report from a ChangeAnalysisResult."""
    stats = result.stats or {}
    n_fatal = stats.get("fatal", 0)
    n_warn = stats.get("warnings", 0)
    n_info = stats.get("info", 0)

    metrics = _summary_metrics([
        (str(stats.get("v1_constraints", 0)), "V1 Constraints", "blue"),
        (str(stats.get("v2_constraints", 0)), "V2 Constraints", "green"),
        (str(stats.get("added", 0)), "Added", "green"),
        (str(stats.get("removed", 0)), "Removed", "red"),
        (str(stats.get("modified", 0)), "Modified", "yellow"),
    ])

    badges = _badge(n_fatal, "Fatal", "red") + _badge(n_warn, "Warnings", "yellow") + _badge(n_info, "Info", "blue")

    # Change cards
    cards = ""
    for c in result.changes:
        sev = c.rule.severity
        cards += f"""<div class="change-card {sev}">
<div><span class="change-sev {sev}">{sev.upper()}</span> <span class="change-rule">[{c.rule.rule_id}]</span> {c.rule.description}</div>
<div style="margin-top:4px;font-size:13px;color:#374151">{c.explanation}</div>"""
        if c.v1_text:
            cards += f'<span class="change-text" style="color:#991b1b">- {c.v1_text}</span>'
        if c.v2_text:
            cards += f'<span class="change-text" style="color:#065f46">+ {c.v2_text}</span>'
        cards += "</div>\n"

    changes_section = f"""<div class="section">
<div class="section-title">Changes ({len(result.changes)})</div>
{cards if cards else '<div class="empty-state">No changes detected.</div>'}
</div>"""

    body = f"""{metrics}
<div class="badge-row">{badges}</div>
{changes_section}"""

    return _page("SDC Change Impact Report", f"{os.path.basename(v1_name)} → {os.path.basename(v2_name)}", body)


# ── Clock Relations Report ──────────────────────────────────────────────────

def generate_clock_report(result, filename: str) -> str:
    """Generate an HTML report from a RelationAnalysisResult."""
    stats = result.stats or {}
    n_mismatch = stats.get("mismatches", 0)
    n_missing = stats.get("missing", 0)

    metrics = _summary_metrics([
        (str(stats.get("clocks", 0)), "Clocks", "blue"),
        (str(stats.get("pairs", 0)), "Pairs", "green"),
        (str(n_mismatch), "Mismatches", "red"),
        (str(n_missing), "Missing", "yellow"),
    ])

    # Mismatch cards
    cards = ""
    for m in result.mismatches:
        sev_css = "warning" if m.severity == "warning" else "info"
        cards += f"""<div class="change-card {sev_css}">
<div><span class="change-sev {sev_css}">{m.severity.upper()}</span> <span class="change-rule">[{m.code}]</span></div>
<div style="margin:4px 0"><b>{m.clock_a}</b> vs <b>{m.clock_b}</b></div>
<div style="font-size:13px;color:#374151">Specified: {m.specified} | Expected: {m.expected}</div>
<div style="font-size:13px;color:#374151;margin-top:2px">{m.msg}</div>
</div>\n"""

    mismatches_section = f"""<div class="section">
<div class="section-title">Issues ({len(result.mismatches)})</div>
{cards if cards else '<div class="empty-state">No mismatches found.</div>'}
</div>"""

    # Clock list
    clk_rows = ""
    for c in result.clocks:
        clk_rows += f"<tr><td><code>{c.name}</code></td><td>{c.period}</td><td>{c.source_port}</td>"
        clk_rows += f"<td>{'✓' if c.is_generated else '-'}</td><td>{c.master_clock if c.is_generated else '-'}</td><td>{'✓' if c.is_virtual else '-'}</td></tr>\n"
    clk_table = _table(["Name", "Period (ns)", "Port", "Generated", "Master", "Virtual"], clk_rows)
    clk_section = f"""<div class="section">
<div class="section-title">Clock Definitions ({len(result.clocks)})</div>
{clk_table}
</div>"""

    # Clock relation matrix
    if result.clocks:
        names = [c.name for c in result.clocks]
        # Build relation lookup
        rel_map: dict[tuple[str, str], str] = {}
        for p in result.pairs:
            rel_map[(p.clock_a, p.clock_b)] = p.inferred_relation
            rel_map[(p.clock_b, p.clock_a)] = p.inferred_relation
        # Build specified lookup
        spec_map: dict[tuple[str, str], str] = {}
        for g in result.existing_groups:
            group_clocks = g.get("clocks", [])
            gtype = g.get("type", "")
            for ca in group_clocks:
                for cb in group_clocks:
                    if ca != cb:
                        spec_map[(ca, cb)] = gtype

        hdr = "<th>Clock</th>" + "".join(f"<th>{n}</th>" for n in names)
        mat_rows = ""
        for ca in names:
            cells = f"<td><b>{ca}</b></td>"
            for cb in names:
                cell_class = ""
                text = "—"
                if ca == cb:
                    cell_class = "matrix-correct"
                else:
                    inferred = rel_map.get((ca, cb), "unknown")
                    specified = spec_map.get((ca, cb), "")
                    if specified:
                        if inferred == specified:
                            cell_class = "matrix-correct"
                            text = "✓"
                        elif (inferred == "physically_exclusive" and specified == "asynchronous") or \
                             (inferred == "synchronous" and specified in ("logically_exclusive", "physically_exclusive")):
                            cell_class = "matrix-mismatch"
                            text = "✗"
                        else:
                            cell_class = "matrix-mismatch"
                            text = "⚠"
                    else:
                        if inferred in ("asynchronous", "physically_exclusive"):
                            cell_class = "matrix-missing"
                            text = "?"
                        else:
                            cell_class = "matrix-sync-missing"
                            text = "~"
                cells += f'<td class="{cell_class}">{text}</td>'
            mat_rows += f"<tr>{cells}</tr>\n"

        legend = """<div class="legend">
<span class="legend-item" style="background:#d1fae5">✓ Correct</span>
<span class="legend-item" style="background:#fee2e2">✗ Mismatch</span>
<span class="legend-item" style="background:#fef3c7">? Missing constraint</span>
<span class="legend-item" style="background:#dbeafe">~ Synchronous (no constraint needed)</span>
</div>"""
        matrix_section = f"""<div class="section">
<div class="section-title">Clock Relation Matrix ({len(names)}×{len(names)})</div>
{legend}
<div class="clock-matrix">{_table(["Clock"] + names, mat_rows)}</div>
</div>"""
    else:
        matrix_section = ""

    body = f"""{metrics}
{mismatches_section}
{clk_section}
{matrix_section}"""

    return _page("SDC Clock Relations Report", os.path.basename(filename), body)


# ── Rules Report ────────────────────────────────────────────────────────────

def generate_rules_report(rules, title: str = "Rules Registry") -> str:
    """Generate an HTML report listing rules from the Rules Registry."""
    rows = ""
    for r in rules:
        sev_css = {"error": "red", "warning": "yellow", "info": "blue", "fatal": "red"}
        badge = f'<span class="badge badge-{sev_css.get(r.severity, "blue")}" style="font-size:11px;padding:1px 8px">{r.severity}</span>'
        rows += f"<tr><td><code>{r.code}</code></td><td>{badge}</td><td>{r.module}</td><td>{r.short_name}</td><td>{r.description[:80]}{'…' if len(r.description) > 80 else ''}</td><td style='font-size:11px;color:#6b7280'>v{r.added_version}</td></tr>\n"

    table = _table(["Code", "Severity", "Module", "Name", "Description", "Added"], rows)
    body = f"""<div class="section">
<div class="section-title">{title} ({len(rules)} rules)</div>
{table}
</div>"""
    return _page(title, f"SDC Tools v{APP_VERSION}", body)


# ── Coverage Report ─────────────────────────────────────────────────────────

_COV_CSS = """
.cov-bar-bg { background: #e5e7eb; border-radius: 6px; height: 14px; width: 100%; position: relative; }
.cov-bar-fill { height: 14px; border-radius: 6px; transition: width 0.3s; }
.cov-bar-fill.good { background: #059669; }
.cov-bar-fill.warn { background: #d97706; }
.cov-bar-fill.bad { background: #dc2626; }
.cov-item-present { color: #059669; font-weight: 600; }
.cov-item-missing { color: #dc2626; font-weight: 600; }
.cov-item-missing.crit { color: #b91c1c; font-weight: 700; }
.cov-cat-header { display: flex; align-items: center; gap: 8px; margin: 16px 0 6px 0; }
.cov-cat-icon { font-size: 18px; }
.cov-cat-title { font-size: 14px; font-weight: 600; }
.cov-cat-score { font-size: 13px; color: #6b7280; }
.cov-score-big { font-size: 48px; font-weight: 800; text-align: center; margin: 10px 0; }
.cov-score-big.good { color: #059669; }
.cov-score-big.warn { color: #d97706; }
.cov-score-big.bad { color: #dc2626; }
.cov-score-label { font-size: 13px; color: #6b7280; text-align: center; margin-bottom: 16px; }
"""


def generate_coverage_report(result, filename: str) -> str:
    """Generate an HTML report from a CoverageResult."""
    css = _CSS + _COV_CSS

    # Overall score
    score_cls = result.score.status if hasattr(result.score, "status") else (
        "good" if result.score >= 80 else "warn" if result.score >= 50 else "bad"
    )
    # Compute status from numeric score
    if result.score >= 80:
        score_cls = "good"
    elif result.score >= 50:
        score_cls = "warn"
    else:
        score_cls = "bad"

    # Summary metrics
    metrics = _summary_metrics([
        (f"{result.score:.0f}%", "Overall Coverage", score_cls),
        (str(result.total_present), "Items Present", "green"),
        (str(result.total_missing), "Items Missing", "red"),
        (str(len(result.categories)), "Categories", "blue"),
    ])

    # Category cards
    cat_cards = ""
    for cat in result.categories:
        bar_cls = cat.status
        bar_pct = cat.score

        items_html = ""
        for item in cat.items:
            if item.present:
                items_html += f'<tr><td><span class="cov-item-present">&#10003;</span></td><td>{item.name}</td><td style="color:#6b7280;font-size:12px">{item.detail}</td></tr>\n'
            else:
                crit_cls = "crit" if item.is_critical else ""
                crit_mark = " <b>*</b>" if item.is_critical else ""
                items_html += f'<tr><td><span class="cov-item-missing {crit_cls}">&#10007;</span></td><td>{item.name}{crit_mark}</td><td style="color:#6b7280;font-size:12px">{item.detail}</td></tr>\n'

        cat_cards += f"""<div class="section">
<div class="cov-cat-header">
  <span class="cov-cat-icon">{cat.icon}</span>
  <span class="cov-cat-title">{cat.name}</span>
  <span class="cov-cat-score">{cat.score:.0f}% ({cat.covered}/{cat.total})</span>
</div>
<div class="cov-bar-bg"><div class="cov-bar-fill {bar_cls}" style="width:{bar_pct:.0f}%"></div></div>
{_table(["", "Constraint", "Detail"], items_html)}
</div>\n"""

    # Missing items summary
    missing_items = ""
    for cat in result.categories:
        for item in cat.items:
            if not item.present:
                crit = " <b>*</b>" if item.is_critical else ""
                missing_items += f'<tr><td><span class="change-sev warning">{cat.name}</span></td><td>{item.name}{crit}</td><td style="color:#6b7280;font-size:12px">{item.detail}</td></tr>\n'

    missing_section = ""
    if missing_items:
        missing_section = f"""<div class="section">
<div class="section-title">Missing Items ({result.total_missing})</div>
{_table(["Category", "Constraint", "Detail"], missing_items)}
</div>"""

    body = f"""{metrics}
<div class="cov-score-big {score_cls}">{result.score:.1f}%</div>
<div class="cov-score-label">Constraint Coverage — {result.total_present} of {result.total_items} items present</div>
{cat_cards}
{missing_section}"""

    return _page("SDC Constraint Coverage Report", os.path.basename(filename), body)