"""
SDC Tools — Command-line interface
Wrap checker, generator, diff, corners, clock relations, and rules into
a Unix-style CLI for terminal use, CI/CD, and script automation.

Usage:
    sdc-tools check sample.sdc
    sdc-tools check sample.sdc --json
    sdc-tools check sample.sdc --junit --output report.xml
    sdc-tools generate --design MY_CHIP --clock clk=5.0:sys_clk > output.sdc
    sdc-tools diff old.sdc new.sdc
    sdc-tools corners list
    sdc-tools corners show "Classic 3-corner (Worst/Typ/Best)"
    sdc-tools analyze clock-relations input.sdc
    sdc-tools rules list
    sdc-tools rules show SDC-060
"""

import argparse
import json
import sys
import os
import textwrap

from rules_registry import APP_VERSION, get_all_rules, get_rule, get_rules_by_module


# ── Output helpers ───────────────────────────────────────────────────────────

class OutputWriter:
    """Collect output lines and optionally write to file."""

    def __init__(self, output_file: str = ""):
        self.lines: list[str] = []
        self.output_file = output_file

    def write(self, text: str = "") -> None:
        self.lines.append(text)

    def writeln(self, text: str = "") -> None:
        self.lines.append(text)

    def flush(self) -> None:
        text = "\n".join(self.lines)
        if self.output_file:
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
            print(text)

    def json_out(self, obj) -> None:
        text = json.dumps(obj, indent=2, default=str)
        if self.output_file:
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write(text)
        else:
            print(text)


def fatal(msg: str, code: int = 1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


# ── Subcommand: check ────────────────────────────────────────────────────────

def cmd_check(args):
    """Validate an SDC file and report errors / warnings / info."""
    from checker import check_sdc

    try:
        text = args.file.read()
    except Exception as e:
        fatal(f"cannot read {args.file.name}: {e}")
    finally:
        args.file.close()

    result = check_sdc(text)

    # Custom rules
    custom_results: list = []
    custom_rulesets: list = []
    if args.custom_rules:
        from custom_rules import load_ruleset, apply_rules
        for rules_path in args.custom_rules:
            try:
                rs = load_ruleset(rules_path)
                custom_rulesets.append(rs)
                custom_results.extend(apply_rules(text, rs))
            except Exception as e:
                print(f"Warning: cannot load custom rules '{rules_path}': {e}", file=sys.stderr)

    out = OutputWriter(args.output)

    if args.json:
        data = {
            "version": APP_VERSION,
            "file": args.file.name,
            "errors": [{"code": i.code, "msg": i.msg} for i in result.errors],
            "warnings": [{"code": i.code, "msg": i.msg} for i in result.warnings],
            "info": [{"code": i.code, "msg": i.msg} for i in result.info],
            "stats": result.stats,
            "summary": {
                "errors": len(result.errors),
                "warnings": len(result.warnings),
                "info": len(result.info),
                "clocks": result.stats.get("clocks", 0),
            },
        }
        if custom_results:
            data["custom_rules"] = [
                {"id": r.rule.id, "name": r.rule.name, "severity": r.rule.severity,
                 "passed": r.passed, "message": r.msg}
                for r in custom_results
            ]
            data["summary"]["custom_rules_total"] = len(custom_results)
            data["summary"]["custom_rules_failed"] = sum(1 for r in custom_results if not r.passed)
        out.json_out(data)

    elif args.junit:
        _write_junit(out, result, args.file.name)

    else:
        # Text table output
        sep = "-" * 60
        out.writeln(f"SDC Tools v{APP_VERSION} — Checker Results")
        out.writeln(f"File: {args.file.name}")
        out.writeln()

        # Summary row
        err_c = len(result.errors)
        warn_c = len(result.warnings)
        info_c = len(result.info)
        clk_c = result.stats.get("clocks", 0)
        out.writeln(f"  {'Errors:':<16} {err_c}")
        out.writeln(f"  {'Warnings:':<16} {warn_c}")
        out.writeln(f"  {'Info:':<16} {info_c}")
        out.writeln(f"  {'Clocks:':<16} {clk_c}")
        out.writeln(sep)

        # Errors
        if result.errors:
            if args.verbose:
                out.writeln(f"\n  ERRORS  ({len(result.errors)}):")
            for i in result.errors:
                out.writeln(f"  [{i.code}] {i.msg}")

        # Warnings
        if result.warnings:
            if args.verbose:
                out.writeln(f"\n  WARNINGS  ({len(result.warnings)}):")
            for i in result.warnings:
                out.writeln(f"  [{i.code}] {i.msg}")

        # Info
        if result.info and args.verbose:
            out.writeln(f"\n  INFO  ({len(result.info)}):")
            for i in result.info:
                out.writeln(f"  [{i.code}] {i.msg}")

        # Stats
        if result.stats and args.verbose:
            out.writeln(f"\n  Stats:")
            for k, v in sorted(result.stats.items()):
                out.writeln(f"    {k}: {v}")

        # Custom rules (text output)
        if custom_results:
            out.writeln(f"\n  Custom Rules ({len(custom_results)} rules):")
            for r in custom_results:
                status = "PASS" if r.passed else "FAIL"
                out.writeln(f"    [{status}] {r.rule.id} — {r.msg}")
            fail_count = sum(1 for r in custom_results if not r.passed)
            out.writeln(f"  Custom rules: {fail_count} failed / {len(custom_results)} total")

    out.flush()
    sys.exit(1 if result.errors else 0)


def _write_junit(out: OutputWriter, result, filename: str):
    """Write JUnit XML for CI integration."""
    import xml.sax.saxutils as saxutils

    total = len(result.errors) + len(result.warnings) + len(result.info)
    out.writeln('<?xml version="1.0" encoding="UTF-8"?>')
    out.writeln(f'<testsuite name="sdc-tools" tests="{total}" errors="{len(result.errors)}" failures="{len(result.warnings)}">')
    out.writeln(f'  <properties><property name="file" value="{saxutils.escape(filename)}"/></properties>')

    for i in result.errors:
        out.writeln(f'  <testcase classname="checker" name="{saxutils.escape(i.code)}">')
        out.writeln(f'    <error message="{saxutils.escape(i.msg)}"/>')
        out.writeln('  </testcase>')

    for i in result.warnings:
        out.writeln(f'  <testcase classname="checker" name="{saxutils.escape(i.code)}">')
        out.writeln(f'    <failure message="{saxutils.escape(i.msg)}"/>')
        out.writeln('  </testcase>')

    for i in result.info:
        out.writeln(f'  <testcase classname="checker" name="{saxutils.escape(i.code)}"/>')

    out.writeln('</testsuite>')


# ── Subcommand: generate ─────────────────────────────────────────────────────

def cmd_generate(args):
    """Generate a complete SDC file from CLI parameters."""
    from generator import SDCParams, ClockDef, generate_sdc

    clocks: list[ClockDef] = []
    for clk_str in args.clock or []:
        parts = clk_str.split("=", 1)
        name = parts[0]
        rest = parts[1] if len(parts) > 1 else "5.0"
        period = 5.0
        port = ""
        if ":" in rest:
            period_str, port = rest.split(":", 1)
            period = float(period_str)
        else:
            period = float(rest)

        clocks.append(ClockDef(
            name=name,
            clk_type="primary",
            port=port or name,
            period=period,
            uncertainty=args.uncertainty,
        ))

    p = SDCParams(
        design_name=args.design,
        sdc_version=args.sdc_version,
        clocks=clocks,
        add_units=True,
        add_oper_cond=args.operating_condition is not None,
        oper_cond_name=args.operating_condition or "",
        add_derate=args.derate,
        derate_cell_early=1.08,
        derate_cell_late=0.92,
        add_ideal_rst=args.ideal_reset,
        rst_port=args.reset_port,
        add_propagated=args.propagated,
        add_scan=args.scan,
        scan_port=args.scan_port,
    )

    sdc_text = generate_sdc(p)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(sdc_text)
        print(f"Written to {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
        print(sdc_text)


# ── Subcommand: diff ─────────────────────────────────────────────────────────

def cmd_diff(args):
    """Compare two SDC files semantically."""
    from constraint_diff import analyze_constraint_changes

    try:
        v1_text = args.v1.read()
        v2_text = args.v2.read()
    except Exception as e:
        fatal(f"cannot read: {e}")
    finally:
        args.v1.close()
        args.v2.close()

    linked_v1 = _load_linked_files(args.linked_v1) if args.linked_v1 else None
    linked_v2 = _load_linked_files(args.linked_v2) if args.linked_v2 else None

    result = analyze_constraint_changes(v1_text, v2_text, linked_v1, linked_v2)
    out = OutputWriter(args.output)

    if args.json:
        data = {
            "version": APP_VERSION,
            "files": {"v1": args.v1.name, "v2": args.v2.name},
            "stats": result.stats,
            "changes": [
                {
                    "rule": c.rule.rule_id,
                    "severity": c.rule.severity,
                    "type": c.constraint_type,
                    "category": c.category,
                    "explanation": c.explanation,
                    "v1_text": c.v1_text,
                    "v2_text": c.v2_text,
                }
                for c in result.changes
            ],
        }
        out.json_out(data)
    else:
        out.writeln(f"SDC Tools v{APP_VERSION} — Constraint Change Analysis")
        out.writeln(f"  V1: {args.v1.name}")
        out.writeln(f"  V2: {args.v2.name}")
        out.writeln()
        out.writeln(f"  {'Constraints V1:':<20} {result.stats.get('v1_constraints', 0)}")
        out.writeln(f"  {'Constraints V2:':<20} {result.stats.get('v2_constraints', 0)}")
        out.writeln(f"  {'Added:':<20} {result.stats.get('added', 0)}")
        out.writeln(f"  {'Removed:':<20} {result.stats.get('removed', 0)}")
        out.writeln(f"  {'Modified:':<20} {result.stats.get('modified', 0)}")
        out.writeln(f"  {'Fatal:':<20} {result.stats.get('fatal', 0)}")
        out.writeln(f"  {'Warnings:':<20} {result.stats.get('warnings', 0)}")
        out.writeln(f"  {'Info:':<20} {result.stats.get('info', 0)}")
        out.writeln()

        for c in result.changes:
            label = f"[{c.rule.rule_id}]"
            out.writeln(f"  {c.rule.severity.upper():>7} {label:<15} {c.explanation}")
            if args.verbose and c.v1_text:
                out.writeln(f"           V1: {c.v1_text[:80]}")
            if args.verbose and c.v2_text:
                out.writeln(f"           V2: {c.v2_text[:80]}")

    out.flush()


def _load_linked_files(paths: list[str]):
    """Load linked TCL files by reading each path directly.

    paths may be specified multiple times: --linked-v1 file1.tcl --linked-v1 file2.tcl
    Returns {filename: content} dict for the constraint_diff API.
    """
    files = {}
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                files[os.path.basename(path)] = f.read()
        except Exception as e:
            print(f"Warning: cannot load linked file '{path}': {e}", file=sys.stderr)
    return files


# ── Subcommand: corners ──────────────────────────────────────────────────────

def cmd_corners(args):
    """Manage and inspect PVT corner presets."""
    from corner_manager import CORNER_PRESETS, corner_matrix, validate_corner

    out = OutputWriter(args.output)

    if args.action == "list":
        out.writeln(f"Available corner presets ({len(CORNER_PRESETS)}):")
        out.writeln()
        for name, corners in CORNER_PRESETS.items():
            if not corners:
                out.writeln(f"  {name}")
            else:
                out.writeln(f"  {name}  ({len(corners)} corners)")

    elif args.action == "show":
        name = args.preset_name
        corners = CORNER_PRESETS.get(name)
        if corners is None:
            # Try partial match
            matches = [k for k in CORNER_PRESETS if name.lower() in k.lower()]
            if len(matches) == 1:
                corners = CORNER_PRESETS[matches[0]]
                name = matches[0]
            elif len(matches) > 1:
                fatal(f"'{name}' matches multiple presets: {matches}")
            else:
                fatal(f"preset '{name}' not found. Use 'corners list' to see available.")

        out.writeln(f"Preset: {name}")
        out.writeln(f"Corners: {len(corners)}")
        out.writeln()

        for c in corners:
            out.writeln(f"  {c.name}")
            out.writeln(f"    Process: {c.process_type}  V={c.voltage:.2f}V  T={c.temperature:.0f}°C")
            out.writeln(f"    Op Cond: {c.operating_condition or '(none)'}")
            out.writeln(f"    Derate:  cell_early={c.derate_cell_early:.3f}  cell_late={c.derate_cell_late:.3f}")
            out.writeln(f"             net_early={c.derate_net_early:.3f}   net_late={c.derate_net_late:.3f}")
            out.writeln(f"    Uncertainty scale: {c.uncertainty_scale:.2f}")
            errors = validate_corner(c)
            if errors:
                for e in errors:
                    out.writeln(f"    ⚠  {e}")
            out.writeln()

    out.flush()


# ── Subcommand: analyze ──────────────────────────────────────────────────────

def cmd_analyze(args):
    """Analyze clock relations in an SDC file."""
    if args.analysis_type == "clock-relations":
        _analyze_clock_relations(args)
    else:
        fatal(f"unknown analysis type: {args.analysis_type}")


def _analyze_clock_relations(args):
    """Analyze clock pairs and detect set_clock_groups mismatches."""
    import clock_relations as cr

    try:
        text = args.file.read()
    except Exception as e:
        fatal(f"cannot read {args.file.name}: {e}")
    finally:
        args.file.close()

    result = cr.analyze_clock_relations(text)
    out = OutputWriter(args.output)

    if args.json:
        data = {
            "version": APP_VERSION,
            "file": args.file.name,
            "stats": result.stats,
            "clocks": [
                {"name": c.name, "period": c.period, "source": c.source_port,
                 "generated": c.is_generated, "virtual": c.is_virtual}
                for c in result.clocks
            ],
            "mismatches": [
                {"code": m.code, "severity": m.severity, "clock_a": m.clock_a,
                 "clock_b": m.clock_b, "specified": m.specified, "expected": m.expected,
                 "message": m.msg}
                for m in result.mismatches
            ],
            "pairs": [
                {"clock_a": p.clock_a, "clock_b": p.clock_b,
                 "inferred": p.inferred_relation, "reason": p.reason}
                for p in result.pairs
            ],
        }
        out.json_out(data)
    else:
        out.writeln(f"SDC Tools v{APP_VERSION} — Clock Relations Analysis")
        out.writeln(f"File: {args.file.name}")
        out.writeln()
        out.writeln(f"  {'Clocks:':<24} {result.stats.get('clocks', 0)}")
        out.writeln(f"  {'Pairs:':<24} {result.stats.get('pairs', 0)}")
        out.writeln(f"  {'Synchronous:':<24} {result.stats.get('synchronous', 0)}")
        out.writeln(f"  {'Asynchronous:':<24} {result.stats.get('asynchronous', 0)}")
        out.writeln(f"  {'Physically Exclusive:':<24} {result.stats.get('physically_exclusive', 0)}")
        out.writeln(f"  {'Mismatches:':<24} {result.stats.get('mismatches', 0)}")
        out.writeln(f"  {'Missing Constraints:':<24} {result.stats.get('missing', 0)}")
        out.writeln()

        if result.mismatches:
            out.writeln("Mismatches:")
            for m in result.mismatches:
                sev_label = "WARN" if m.severity == "warning" else "INFO"
                out.writeln(f"  [{m.code}] {sev_label}  {m.clock_a} vs {m.clock_b}")
                out.writeln(f"          Specified: {m.specified}")
                out.writeln(f"          Expected:  {m.expected}")
                out.writeln(f"          {m.msg}")
                out.writeln()

        if result.pairs and args.verbose:
            out.writeln("All Clock Pairs:")
            for p in result.pairs:
                out.writeln(f"  {p.clock_a:<20}  {p.clock_b:<20}  {p.inferred_relation:<22}  ({p.reason[:50]})")

        # Clock definitions
        if args.verbose:
            out.writeln("\nClock Definitions:")
            for c in result.clocks:
                gen = f"  gen={c.master_clock}/{c.divide_by}" if c.is_generated else ""
                virt = "  VIRTUAL" if c.is_virtual else ""
                out.writeln(f"  {c.name:<20}  period={c.period:<8}  port={c.source_port}{gen}{virt}")

    out.flush()


# ── Subcommand: rules ────────────────────────────────────────────────────────

def cmd_rules(args):
    """Look up rule codes from the Rules Registry."""
    out = OutputWriter(args.output)

    if args.action == "list":
        rules = get_all_rules()

        # Filter by module
        if args.module:
            rules = [r for r in rules if r.module == args.module]

        # Filter by severity
        if args.severity:
            rules = [r for r in rules if r.severity == args.severity]

        # Search
        if args.search:
            q = args.search.lower()
            rules = [r for r in rules if q in r.code.lower() or q in r.short_name.lower() or q in r.description.lower()]

        if args.json:
            data = [
                {"code": r.code, "severity": r.severity, "name": r.short_name,
                 "module": r.module, "description": r.description, "added": r.added_version}
                for r in rules
            ]
            out.json_out(data)
        else:
            out.writeln(f"SDC Tools v{APP_VERSION} — Rules Registry ({len(rules)} rules)")
            if args.module or args.severity or args.search:
                filters = []
                if args.module:
                    filters.append(f"module={args.module}")
                if args.severity:
                    filters.append(f"severity={args.severity}")
                if args.search:
                    filters.append(f"search='{args.search}'")
                out.writeln(f"  Filters: {', '.join(filters)}")
            out.writeln()
            out.writeln(f"  {'Code':<16} {'Sev':>7} {'Module':<18} {'Name'}")
            out.writeln(f"  {'-'*16} {'-'*7} {'-'*18} {'-'*40}")
            for r in rules:
                out.writeln(f"  {r.code:<16} {r.severity:>7} {r.module:<18} {r.short_name}")

    elif args.action == "show":
        code = args.code.upper()
        rule = get_rule(code)
        if not rule:
            fatal(f"rule '{code}' not found. Use 'rules list' to see available.")
        if args.json:
            out.json_out({
                "code": rule.code,
                "severity": rule.severity,
                "name": rule.short_name,
                "description": rule.description,
                "why_matters": rule.why_matters,
                "fix": rule.fix,
                "module": rule.module,
                "added_version": rule.added_version,
                "reference_url": rule.reference_url,
            })
        else:
            out.writeln(f"  Code:       {rule.code}")
            out.writeln(f"  Severity:   {rule.severity}")
            out.writeln(f"  Name:       {rule.short_name}")
            out.writeln(f"  Module:     {rule.module}")
            out.writeln(f"  Added:      v{rule.added_version}")
            out.writeln(f"  Description: {rule.description}")
            out.writeln(f"  Why:        {rule.why_matters}")
            out.writeln(f"  Fix:        {rule.fix}")
            if rule.reference_url:
                out.writeln(f"  Reference:  {rule.reference_url}")

    out.flush()


# ── Subcommand: coverage ─────────────────────────────────────────────────────

def cmd_coverage(args):
    """Analyze constraint coverage in an SDC file."""
    from coverage import parse_sdc_coverage

    try:
        text = args.file.read()
    except Exception as e:
        fatal(f"cannot read {args.file.name}: {e}")
    finally:
        args.file.close()

    result = parse_sdc_coverage(text, args.file.name)
    out = OutputWriter(args.output)

    if args.json:
        data = {
            "version": APP_VERSION,
            "file": args.file.name,
            "score_pct": round(result.score, 1),
            "total_items": result.total_items,
            "total_present": result.total_present,
            "total_missing": result.total_missing,
            "categories": [
                {
                    "name": cat.name,
                    "score": round(cat.score, 1),
                    "covered": cat.covered,
                    "total": cat.total,
                    "missing": cat.missing,
                    "items": [
                        {"name": it.name, "present": it.present, "critical": it.is_critical, "detail": it.detail}
                        for it in cat.items
                    ],
                }
                for cat in result.categories
            ],
        }
        out.json_out(data)
    else:
        out.writeln(f"SDC Tools v{APP_VERSION} — Constraint Coverage Analysis")
        out.writeln(f"File: {args.file.name}")
        out.writeln()
        out.writeln(f"  Overall Coverage: {result.score:.1f}%  ({result.total_present}/{result.total_items} items)")
        out.writeln(f"  Missing: {result.total_missing}")
        out.writeln("-" * 60)

        if args.missing_only:
            # Compact: only show missing items
            for cat in result.categories:
                missing = [it for it in cat.items if not it.present]
                if missing:
                    out.writeln(f"\n  {cat.icon} {cat.name}: {cat.score:.0f}%  ({cat.covered}/{cat.total})")
                    for item in missing:
                        crit = " *" if item.is_critical else ""
                        out.writeln(f"    [N] {item.name}{crit}")
                        if item.detail:
                            out.writeln(f"         {item.detail}")
        else:
            # Full output: show all categories
            for cat in result.categories:
                bar = _bar_chart(cat.score)
                out.writeln(f"\n  {cat.icon} {cat.name}: {cat.score:.0f}%  {bar}  ({cat.covered}/{cat.total})")
                for item in cat.items:
                    mark = "Y" if item.present else "N"
                    crit = " *" if item.is_critical and not item.present else ""
                    out.writeln(f"    [{mark}] {item.name}{crit}")
                    if item.detail:
                        out.writeln(f"         {item.detail}")

    out.flush()


def _bar_chart(pct: float, width: int = 20) -> str:
    """Simple ASCII bar chart: [████████░░░░░░░░░░░░]"""
    filled = int(pct / 100 * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


# ── Subcommand: web ───────────────────────────────────────────────────────────

def cmd_web(args):
    """Launch the Streamlit web UI."""
    import subprocess
    import sys
    print("Starting SDC Tools Web UI...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])


# ── Subcommand: report ───────────────────────────────────────────────────────

def cmd_report(args):
    """Generate formatted signoff reports (HTML)."""
    from reporter import generate_check_report, generate_diff_report, generate_clock_report, generate_coverage_report

    if args.report_type == "check":
        from checker import check_sdc
        try:
            text = args.file.read()
        except Exception as e:
            fatal(f"cannot read {args.file.name}: {e}")
        finally:
            args.file.close()

        result = check_sdc(text)
        html = generate_check_report(result, args.file.name, verbose=args.verbose)
        _write_report(html, args.output)

    elif args.report_type == "diff":
        from constraint_diff import analyze_constraint_changes

        linked_v1 = _load_linked_files(getattr(args, "linked_v1", [])) if getattr(args, "linked_v1", None) else None
        linked_v2 = _load_linked_files(getattr(args, "linked_v2", [])) if getattr(args, "linked_v2", None) else None
        v1_name = getattr(args, "v1_name", None) or (getattr(args, "v1", None) and args.v1.name)
        v2_name = getattr(args, "v2_name", None) or (getattr(args, "v2", None) and args.v2.name)

        try:
            v1_text = args.v1.read()
            v2_text = args.v2.read()
        except Exception as e:
            fatal(f"cannot read diff files: {e}")
        finally:
            args.v1.close()
            args.v2.close()

        result = analyze_constraint_changes(v1_text, v2_text, linked_v1, linked_v2)
        html = generate_diff_report(result, v1_name or "", v2_name or "")
        _write_report(html, args.output)

    elif args.report_type == "clock-relations":
        import clock_relations as cr

        try:
            text = args.cr_file.read()
        except Exception as e:
            fatal(f"cannot read {args.cr_file.name}: {e}")
        finally:
            args.cr_file.close()

        result = cr.analyze_clock_relations(text)
        html = generate_clock_report(result, args.cr_file.name)
        _write_report(html, args.output)

    elif args.report_type == "coverage":
        from coverage import parse_sdc_coverage

        try:
            text = args.cov_file.read()
        except Exception as e:
            fatal(f"cannot read {args.cov_file.name}: {e}")
        finally:
            args.cov_file.close()

        result = parse_sdc_coverage(text, args.cov_file.name)
        html = generate_coverage_report(result, args.cov_file.name)
        _write_report(html, args.output)

    else:
        fatal(f"unknown report type: {args.report_type}")


def _write_report(html: str, output_path: str):
    """Write HTML to file or stdout."""
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Written to {output_path}")
    else:
        sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
        print(html)


# ── Main CLI ─────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdc-tools",
        description="SDC constraint development & verification toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              sdc-tools check sample.sdc
              sdc-tools check sample.sdc --json
              sdc-tools check sample.sdc --junit --output results.xml
              sdc-tools generate --design MY_CHIP --clock clk=10.0:sys_clk > output.sdc
              sdc-tools diff old.sdc new.sdc
              sdc-tools corners list
              sdc-tools corners show "Classic 3-corner"
              sdc-tools analyze clock-relations input.sdc
              sdc-tools rules list --module checker
              sdc-tools rules show SDC-060
        """),
    )
    parser.add_argument("--version", action="version", version=f"SDC Tools v{APP_VERSION}")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # ── check ──
    p_check = sub.add_parser("check", help="Validate an SDC file", description="Parse and validate an SDC file, reporting errors, warnings, and best-practice suggestions.")
    p_check.add_argument("file", type=argparse.FileType("r", encoding="utf-8"), help="Path to .sdc file")
    p_check.add_argument("--json", action="store_true", help="Output JSON")
    p_check.add_argument("--junit", action="store_true", help="Output JUnit XML (for CI)")
    p_check.add_argument("--output", "-o", default="", help="Write output to file instead of stdout")
    p_check.add_argument("--verbose", "-v", action="store_true", help="Show info items and stats")
    p_check.add_argument("--custom-rules", action="append", default=[], metavar="YAML", help="Path to custom rules YAML file (repeatable)")

    # ── generate ──
    p_gen = sub.add_parser("generate", help="Generate an SDC file", description="Generate a complete synthesis-ready SDC file from CLI parameters.")
    p_gen.add_argument("--design", "-d", default="MY_DESIGN", help="Design name (default: MY_DESIGN)")
    p_gen.add_argument("--clock", "-c", action="append", default=[], metavar="NAME=PERIOD[:PORT]", help="Add a clock, e.g. clk=10.0:sys_clk")
    p_gen.add_argument("--uncertainty", "-u", type=float, default=0.15, help="Clock uncertainty in ns (default: 0.15)")
    p_gen.add_argument("--sdc-version", default="2.2", help="SDC version (default: 2.2)")
    p_gen.add_argument("--operating-condition", default="", help="Operating condition name")
    p_gen.add_argument("--derate", action="store_true", help="Add AOCV timing derate")
    p_gen.add_argument("--ideal-reset", action="store_true", help="Add set_ideal_network + set_false_path on reset")
    p_gen.add_argument("--reset-port", default="rst_n", help="Reset port name (default: rst_n)")
    p_gen.add_argument("--propagated", action="store_true", help="Add set_propagated_clock")
    p_gen.add_argument("--scan", action="store_true", help="Add DFT scan mode case analysis")
    p_gen.add_argument("--scan-port", default="scan_mode", help="Scan port name (default: scan_mode)")
    p_gen.add_argument("--output", "-o", default="", help="Output file path")

    # ── diff ──
    p_diff = sub.add_parser("diff", help="Compare two SDC files (semantic diff)", description="Detect hidden changes between SDC versions with semantic constraint comparison, TCL variable resolution, and wildcard drift detection.")
    p_diff.add_argument("v1", type=argparse.FileType("r", encoding="utf-8"), help="First (older) SDC file")
    p_diff.add_argument("v2", type=argparse.FileType("r", encoding="utf-8"), help="Second (newer) SDC file")
    p_diff.add_argument("--linked-v1", action="append", default=[], metavar="FILE", help="TCL file with V1 variable definitions (repeatable)")
    p_diff.add_argument("--linked-v2", action="append", default=[], metavar="FILE", help="TCL file with V2 variable definitions (repeatable)")
    p_diff.add_argument("--json", action="store_true", help="Output JSON")
    p_diff.add_argument("--output", "-o", default="", help="Write output to file")
    p_diff.add_argument("--verbose", "-v", action="store_true", help="Show V1/V2 text for changes")

    # ── corners ──
    p_corners = sub.add_parser("corners", help="List / inspect PVT corner presets", description="Manage and inspect predefined PVT timing corner collections.")
    p_corners.add_argument("action", choices=["list", "show"], help="list: available presets; show: preset details")
    p_corners.add_argument("preset_name", nargs="?", default="", help="Preset name to show (partial match OK)")
    p_corners.add_argument("--output", "-o", default="", help="Write output to file")

    # ── analyze ──
    p_analyze = sub.add_parser("analyze", help="Analyze clock relations / constraints", description="Deep analysis of SDC content such as clock relation inference and mismatch detection.")
    p_analyze.add_argument("analysis_type", choices=["clock-relations"], help="Type of analysis")
    p_analyze.add_argument("file", type=argparse.FileType("r", encoding="utf-8"), help="SDC file to analyze")
    p_analyze.add_argument("--json", action="store_true", help="Output JSON")
    p_analyze.add_argument("--output", "-o", default="", help="Write output to file")
    p_analyze.add_argument("--verbose", "-v", action="store_true", help="Show all clock pairs and definitions")

    # ── rules ──
    p_rules = sub.add_parser("rules", help="Look up rule codes from the Rules Registry", description="Search, list, and inspect all SDC-NNN, CHG-XXX-NNN rule codes with descriptions and engineering context.")
    p_rules.add_argument("action", choices=["list", "show"], help="list: all rules; show: single rule details")
    p_rules.add_argument("code", nargs="?", default="", help="Rule code, e.g. SDC-060 (for show)")
    p_rules.add_argument("--module", "-m", default="", help="Filter by module: checker, mmc, clock_relations, constraint_diff")
    p_rules.add_argument("--severity", "-s", default="", help="Filter by severity: error, warning, info, fatal")
    p_rules.add_argument("--search", default="", help="Search text in code, name, description")
    p_rules.add_argument("--json", action="store_true", help="Output JSON")
    p_rules.add_argument("--output", "-o", default="", help="Write output to file")

    # ── web ──
    sub.add_parser("web", help="Launch the Streamlit web UI",
                   description="Launch the SDC Tools web interface in your browser.")

    # ── coverage ──
    p_cov = sub.add_parser("coverage", help="Analyze constraint coverage", description="Measure which constraint categories are covered vs. missing in an SDC file — gap analysis for signoff readiness.")
    p_cov.add_argument("file", type=argparse.FileType("r", encoding="utf-8"), help="SDC file to analyze")
    p_cov.add_argument("--json", action="store_true", help="Output JSON")
    p_cov.add_argument("--missing-only", action="store_true", help="Show only missing items")
    p_cov.add_argument("--output", "-o", default="", help="Write output to file")

    # ── report ──
    p_report = sub.add_parser("report", help="Generate HTML signoff reports", description="Generate professional HTML signoff reports from checker, diff, or analysis results.")
    rsub = p_report.add_subparsers(dest="report_type", help="Report type")

    # report check
    p_rcheck = rsub.add_parser("check", help="SDC quality report")
    p_rcheck.add_argument("file", type=argparse.FileType("r", encoding="utf-8"), help="SDC file to report on")
    p_rcheck.add_argument("--verbose", "-v", action="store_true", help="Include info-level items in report")
    p_rcheck.add_argument("--output", "-o", default="", help="Output HTML file")

    # report diff
    p_rdiff = rsub.add_parser("diff", help="SDC change impact report")
    p_rdiff.add_argument("v1", type=argparse.FileType("r", encoding="utf-8"), help="First (older) SDC file")
    p_rdiff.add_argument("v2", type=argparse.FileType("r", encoding="utf-8"), help="Second (newer) SDC file")
    p_rdiff.add_argument("--v1-name", default="", help="Label for V1 (default: filename)")
    p_rdiff.add_argument("--v2-name", default="", help="Label for V2 (default: filename)")
    p_rdiff.add_argument("--linked-v1", action="append", default=[], metavar="FILE", help="TCL file with V1 variable definitions (repeatable)")
    p_rdiff.add_argument("--linked-v2", action="append", default=[], metavar="FILE", help="TCL file with V2 variable definitions (repeatable)")
    p_rdiff.add_argument("--output", "-o", default="", help="Output HTML file")

    # report clock-relations
    p_rcr = rsub.add_parser("clock-relations", help="Clock relations analysis report")
    p_rcr.add_argument("cr_file", metavar="file", type=argparse.FileType("r", encoding="utf-8"), help="SDC file to analyze")
    p_rcr.add_argument("--output", "-o", default="", help="Output HTML file")

    # report coverage
    p_rcov = rsub.add_parser("coverage", help="Constraint coverage analysis report")
    p_rcov.add_argument("cov_file", metavar="file", type=argparse.FileType("r", encoding="utf-8"), help="SDC file to analyze")
    p_rcov.add_argument("--output", "-o", default="", help="Output HTML file")

    return parser


def main(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Dispatch
    dispatch = {
        "check": cmd_check,
        "generate": cmd_generate,
        "diff": cmd_diff,
        "corners": cmd_corners,
        "analyze": cmd_analyze,
        "rules": cmd_rules,
        "coverage": cmd_coverage,
        "report": cmd_report,
        "web": cmd_web,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()