"""
SDC Tools — Streamlit App
Checker + Generator + MMC Corner Manager for synthesis design constraint files.
"""

from typing import Dict
import difflib
import streamlit as st
from checker import check_sdc
from generator import (
    SDCParams, ClockDef, FalsePath, MultiCyclePath,
    HalfCyclePath, CaseAnalysisEntry, DisableArc,
    PathGroup, generate_sdc
)
from corner_manager import (
    Corner, CORNER_PRESETS, validate_corner,
    corner_to_dict, corner_from_dict, corners_to_json, corners_from_json,
    corner_matrix,
)
from mmc import generate_corner_sdcs, diff_corners, check_sdc_multi, create_corner_zip
from constraint_diff import analyze_constraint_changes
import clock_relations
from rules_registry import (
    APP_VERSION, get_all_rules, get_rules_by_module,
    get_rules_by_severity, get_rule,
)
from coverage import parse_sdc_coverage

st.set_page_config(
    page_title="SDC Tools",
    page_icon="🔧",
    layout="wide",
)

# ── Sidebar — version + changelog ─────────────────────────────────────────────
with st.sidebar:
    st.divider()
    st.caption(f"**SDC Tools** v{APP_VERSION}")
    with st.expander("📋 What's New"):
        st.markdown(f"""
**v{APP_VERSION}**
- **Clock Relations tab** — detect incorrect `set_clock_groups` (SDC-060..063)
- **Rule Reference** — searchable table of all checker codes with docs
- **MMC integration** in SDC Generator — live validation + multi-corner + baseline compare

**v1.1.0**
- **Constraint Change Analyzer** — semantic SDC diff with TCL variable resolution
- **MMC SDC Generator** — per-corner generation with cross-corner checks
- **MMC Corner Manager** — PVT corner presets and validation
""")
    st.caption("© RAMA-L7 · [GitHub](https://github.com/RAMA-L7/sdc-tools)")

# ── Session state initialization ───────────────────────────────────────────────
if "corners" not in st.session_state:
    st.session_state.corners = []
if "generated_sdcs" not in st.session_state:
    st.session_state.generated_sdcs = {}
if "editing_corner_idx" not in st.session_state:
    st.session_state.editing_corner_idx = None
if "analyzer_result" not in st.session_state:
    st.session_state.analyzer_result = None

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: 600; }
.err-badge  { background:#FCEBEB; color:#A32D2D; border:1px solid #F09595; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.warn-badge { background:#FAEEDA; color:#633806; border:1px solid #FAC775; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.info-badge { background:#E6F1FB; color:#0C447C; border:1px solid #85B7EB; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.note-badge { background:#EAF3DE; color:#27500A; border:1px solid #97C459; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.fatal-badge { background:#FDE2E2; color:#7F1D1D; border:1px solid #F87171; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
code { font-family: monospace; background:#f3f4f6; padding:1px 6px; border-radius:4px; font-size:12px; }
</style>
""", unsafe_allow_html=True)

st.title("🔧 SDC Tools")
st.caption("Validate existing constraints · Generate a complete SDC for your design")

tab_checker, tab_generator, tab_mmc_mgr, tab_mmc_gen, tab_analyzer, tab_clock_rel, tab_coverage = st.tabs([
    "🛡 Checker / Validator",
    "⚙️ SDC Generator",
    "🔲 MMC Corner Manager",
    "📦 MMC SDC Generator",
    "🔍 Constraint Change Analyzer",
    "🕐 Clock Relations",
    "📊 Coverage",
])


# ════════════════════════════════════════════════════════════════════════════
# CHECKER TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_checker:
    st.subheader("SDC Checker")
    st.write("Upload your .sdc file or paste the content below to validate it.")

    col_up, col_paste = st.columns([1, 2])

    with col_up:
        uploaded = st.file_uploader("Upload .sdc / .tcl / .txt", type=["sdc", "tcl", "txt"])

    with col_paste:
        pasted = st.text_area(
            "Or paste SDC text here",
            height=160,
            placeholder=(
                "set sdc_version 2.2\n"
                "set_units -time ns -capacitance pF\n"
                "create_clock -name clk_core -period 5.0 [get_ports clk]\n"
                "set_clock_uncertainty -setup 0.15 [get_clocks clk_core]\n"
                "..."
            ),
        )

    sdc_text = None
    filename = "pasted.sdc"

    if uploaded:
        sdc_text = uploaded.read().decode("utf-8", errors="replace")
        filename = uploaded.name
    elif pasted.strip():
        sdc_text = pasted

    if sdc_text:
        # ── Custom Rules upload ───────────────────────────────────────────────
        custom_rule_results = []
        cr_uploaded = st.file_uploader("📋 Custom Rules YAML (optional)", type=["yaml", "yml"],
                                       key="cr_checker_upload",
                                       help="Upload a custom rules YAML file to run alongside the built-in checker")
        if cr_uploaded:
            try:
                import yaml
                cr_data = cr_uploaded.read().decode("utf-8")
                from custom_rules import load_ruleset, apply_rules
                import tempfile, os
                tmp = os.path.join(tempfile.gettempdir(), cr_uploaded.name)
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(cr_data)
                rs = load_ruleset(tmp)
                custom_rule_results = apply_rules(sdc_text, rs)
            except Exception as cr_err:
                st.warning(f"Custom rules not loaded: {cr_err}")

        result = check_sdc(sdc_text)
        errors   = result.errors
        warnings = result.warnings

        # ── Summary cards ────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("❌ Errors",   len(errors))
        c2.metric("⚠️ Warnings", len(warnings))
        c3.metric("ℹ️ Info tips", len(result.info))
        c4.metric("🕐 Clocks",   result.stats.get("Clocks", 0))

        # ── Verdict ──────────────────────────────────────────────────────────
        if errors:
            st.error(f"**{len(errors)} error{'s' if len(errors)!=1 else ''} must be fixed** before synthesis will work correctly.")
        elif warnings:
            st.warning(f"No errors, but **{len(warnings)} warning{'s' if len(warnings)!=1 else ''}** need review.")
        else:
            st.success("✅ SDC looks clean — no errors or warnings found.")

        # ── Issues ───────────────────────────────────────────────────────────
        if result.issues:
            st.subheader(f"Issues ({len(result.issues)}) — {filename}")
            for issue in result.issues:
                icon = "🔴" if issue.sev == "error" else "🟡"
                label = "Error" if issue.sev == "error" else "Warning"
                with st.expander(f"{icon} `{issue.code}` — {issue.msg[:80]}{'…' if len(issue.msg)>80 else ''}"):
                    badge_cls = "err-badge" if issue.sev == "error" else "warn-badge"
                    st.markdown(f'<span class="{badge_cls}">{label}</span>', unsafe_allow_html=True)
                    st.write(issue.msg)

        # ── Info ─────────────────────────────────────────────────────────────
        if result.info:
            st.subheader(f"Best practice suggestions ({len(result.info)})")
            for item in result.info:
                with st.expander(f"ℹ️ `{item.code}` — {item.msg[:80]}{'…' if len(item.msg)>80 else ''}"):
                    st.markdown(f'<span class="info-badge">Info</span>', unsafe_allow_html=True)
                    st.write(item.msg)

        # ── Stats ─────────────────────────────────────────────────────────────
        with st.expander("📊 SDC contents summary"):
            cols = st.columns(4)
            for i, (k, v) in enumerate(result.stats.items()):
                cols[i % 4].metric(k, v)

        # ── Custom Rules Results ───────────────────────────────────────────
        if custom_rule_results:
            st.divider()
            with st.expander("📋 **Custom Rules Results**", expanded=True):
                passed = sum(1 for r in custom_rule_results if r.passed)
                failed = sum(1 for r in custom_rule_results if not r.passed)
                st.caption(f"{passed} passed, {failed} failed out of {len(custom_rule_results)} custom rules")
                for r in custom_rule_results:
                    icon = "✅" if r.passed else "❌"
                    sev = {"error": "🔴", "warning": "🟡", "info": "ℹ️"}.get(r.rule.severity, "")
                    with st.expander(f"{icon} `{r.rule.id}` — {r.msg[:100]}"):
                        st.markdown(f"**Rule:** {r.rule.name}")
                        st.markdown(f"**Severity:** {sev} {r.rule.severity}")
                        st.markdown(f"**Description:** {r.rule.description}")
                        st.markdown(f"**Status:** {'✅ Passed' if r.passed else '❌ Failed'}")
                        if not r.passed:
                            st.warning(r.msg)

        # ── Rule Reference ────────────────────────────────────────────────────
        st.divider()
        with st.expander("📋 **Rule Reference** — All Checker Codes", expanded=False):
            st.caption(f"{len(get_all_rules())} rules across 4 modules · Search by code, name, or keyword")
            _ref_search = st.text_input(
                "Search rules",
                placeholder="SDC-060, clock, derate, multicycle...",
                key="rule_ref_search",
            )
            _all_rules = get_all_rules()
            if _ref_search:
                _q = _ref_search.lower()
                _all_rules = [r for r in _all_rules if _q in r.code.lower() or _q in r.short_name.lower() or _q in r.description.lower() or _q in r.why_matters.lower()]

            _mod_filter = st.radio(
                "Filter by module",
                ["All", "checker", "mmc", "clock_relations", "constraint_diff"],
                horizontal=True, key="rule_ref_mod",
            )
            if _mod_filter != "All":
                _all_rules = [r for r in _all_rules if r.module == _mod_filter]

            st.caption(f"Showing **{len(_all_rules)}** rules")
            for _rule in _all_rules:
                _sev_icon = {"error": "🔴", "warning": "🟡", "info": "🔵", "fatal": "💀"}.get(_rule.severity, "⚪")
                _label = f"{_sev_icon} **{_rule.code}** — {_rule.short_name}"
                with st.expander(_label):
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.markdown(f"**Severity:** {_rule.severity}")
                        st.markdown(f"**Module:** {_rule.module}")
                        st.markdown(f"**Added in:** v{_rule.added_version}")
                    with c2:
                        st.markdown(f"**What it detects:** {_rule.description}")
                    st.markdown(f"**Why it matters:** {_rule.why_matters}")
                    st.markdown(f"**How to fix:** {_rule.fix}")
                    if _rule.reference_url:
                        st.markdown(f"📚 **Reference:** [{_rule.reference_url}]({_rule.reference_url})")
    else:
        st.info("Upload a file or paste SDC text above to start checking.")


# ════════════════════════════════════════════════════════════════════════════
# GENERATOR TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_generator:
    st.subheader("SDC Generator")

    left, right = st.columns([1, 1], gap="large")

    with left:

        # ── Header ───────────────────────────────────────────────────────────
        with st.expander("📄 File header", expanded=True):
            g_design  = st.text_input("Design name", value="MY_DESIGN")
            g_sdc_ver = st.selectbox("SDC version", ["2.2", "2.1", "2.0", "1.9"], index=0)
            g_units   = st.checkbox("Add set_units", value=True)
            if g_units:
                uc1, uc2, uc3 = st.columns(3)
                g_time_u = uc1.selectbox("Time", ["ns", "ps"], index=0, key="tu")
                g_cap_u  = uc2.selectbox("Cap",  ["pF", "fF"], index=0, key="cu")
                g_res_u  = uc3.selectbox("Res",  ["kOhm", "Ohm"], index=0, key="ru")
            else:
                g_time_u, g_cap_u, g_res_u = "ns", "pF", "kOhm"

        # ── Clocks ───────────────────────────────────────────────────────────
        with st.expander("🕐 Clock definitions", expanded=True):
            n_clocks = st.number_input("Number of clocks", min_value=1, max_value=8, value=1, step=1)
            g_clocks = []
            for i in range(int(n_clocks)):
                st.markdown(f"**Clock {i+1}**")
                cc1, cc2, cc3 = st.columns([1, 1, 1])
                clk_name = cc1.text_input("Name", value=f"clk_{'core' if i==0 else f'div{i}'}", key=f"cn{i}")
                clk_type = cc2.selectbox("Type", ["primary", "generated", "virtual"], key=f"ct{i}")
                clk_unc  = cc3.number_input("Uncertainty (ns)", value=0.15, step=0.01, format="%.3f", key=f"cu2{i}")

                if clk_type == "primary":
                    p1, p2, p3 = st.columns(3)
                    clk_port = p1.text_input("Port", value="clk" if i==0 else f"clk{i}", key=f"cp{i}")
                    clk_per  = p2.number_input("Period (ns)", value=5.0 if i==0 else 10.0, step=0.1, format="%.3f", key=f"cper{i}")
                    clk_dc   = p3.number_input("Duty cycle %", value=50.0, step=1.0, format="%.1f", key=f"cdc{i}")
                    g_clocks.append(ClockDef(
                        name=clk_name, clk_type="primary", port=clk_port,
                        period=clk_per, uncertainty=clk_unc,
                        duty_cycle=clk_dc if clk_dc != 50.0 else None,
                    ))

                elif clk_type == "virtual":
                    vp = st.number_input("Period (ns)", value=10.0, step=0.1, format="%.3f", key=f"vper{i}")
                    g_clocks.append(ClockDef(
                        name=clk_name, clk_type="virtual", period=vp, uncertainty=clk_unc,
                    ))

                else:  # generated
                    g1, g2, g3 = st.columns(3)
                    gen_port   = g1.text_input("Output port", value=f"clk_gen{i}", key=f"gp{i}")
                    gen_master = g2.text_input("-source (master port)", value="clk", key=f"gm{i}")
                    gen_div    = g3.number_input("-divide_by", value=2, min_value=1, step=1, key=f"gd{i}")
                    g4, g5, g6 = st.columns(3)
                    gen_mul    = g4.number_input("-multiply_by (0=off)", value=0, min_value=0, step=1, key=f"gmu{i}")
                    gen_dc2    = g5.number_input("Duty cycle % (0=off)", value=0.0, step=1.0, key=f"gdc{i}")
                    gen_shift  = g6.text_input("-edge_shift list", value="", placeholder="0 0 0", key=f"ges{i}")
                    gf1, gf2, gf3, gf4 = st.columns(4)
                    gen_inv    = gf1.checkbox("-invert",      key=f"gi{i}")
                    gen_preinv = gf2.checkbox("-preinvert",   key=f"gpi{i}")
                    gen_comb   = gf3.checkbox("-combinational", key=f"gc{i}")
                    gen_add    = gf4.checkbox("-add",         key=f"ga{i}")
                    g_clocks.append(ClockDef(
                        name=clk_name, clk_type="generated",
                        port=gen_port, master_port=gen_master,
                        divide_by=gen_div,
                        multiply_by=gen_mul if gen_mul > 0 else None,
                        uncertainty=clk_unc,
                        duty_cycle=gen_dc2 if gen_dc2 > 0 else None,
                        edge_shift=gen_shift,
                        invert=gen_inv, preinvert=gen_preinv,
                        combinational=gen_comb, add_flag=gen_add,
                    ))
                st.divider()

            # Clock attributes
            st.markdown("**Clock attributes**")
            a1, a2 = st.columns(2)
            g_add_lat  = a1.checkbox("Clock latency")
            g_lat_val  = a1.number_input("Latency (ns)", value=0.5, step=0.1, format="%.2f") if g_add_lat else 0.5
            g_add_prop = a2.checkbox("set_propagated_clock")
            b1, b2 = st.columns(2)
            g_add_trans = b1.checkbox("Clock transition")
            g_trans_val = b1.number_input("Transition (ns)", value=0.1, step=0.01, format="%.3f") if g_add_trans else 0.1
            g_add_jitter = b2.checkbox("Clock jitter -cycle")
            g_jitter_val = b2.number_input("Jitter (ns)", value=0.05, step=0.01, format="%.3f") if g_add_jitter else 0.05
            g_add_gate = st.checkbox("Clock gating check")
            if g_add_gate:
                gc1, gc2 = st.columns(2)
                g_gate_setup = gc1.number_input("Setup (ns)", value=0.5, step=0.1, format="%.2f")
                g_gate_hold  = gc2.number_input("Hold (ns)",  value=0.2, step=0.1, format="%.2f")
            else:
                g_gate_setup, g_gate_hold = 0.5, 0.2

        # ── I/O constraints ──────────────────────────────────────────────────
        with st.expander("🔌 I/O constraints", expanded=True):
            io1, io2 = st.columns(2)
            g_in_max  = io1.number_input("Input delay -max (ns)",  value=1.2, step=0.1, format="%.2f")
            g_in_min  = io2.number_input("Input delay -min (ns)",  value=0.4, step=0.1, format="%.2f")
            g_out_max = io1.number_input("Output delay -max (ns)", value=1.5, step=0.1, format="%.2f")
            g_out_min = io2.number_input("Output delay -min (ns)", value=0.5, step=0.1, format="%.2f")
            d1, d2 = st.columns(2)
            g_add_drive = d1.checkbox("set_driving_cell", value=True)
            g_add_intrans = d2.checkbox("set_input_transition (alternative to driving_cell)")
            if g_add_drive and not g_add_intrans:
                g_drive_cell = st.text_input("Cell name", value="BUF_X4")
            else:
                g_drive_cell = "BUF_X4"
            if g_add_intrans and not g_add_drive:
                g_intrans_val = st.number_input("Transition (ns)", value=0.1, step=0.01, format="%.3f")
            else:
                g_intrans_val = 0.1
            g_add_load = st.checkbox("set_load", value=True)
            g_load_val = st.number_input("Load (pF)", value=0.05, step=0.01, format="%.3f") if g_add_load else 0.05

        # ── Design rules ─────────────────────────────────────────────────────
        with st.expander("📐 Design rule constraints", expanded=True):
            dr1, dr2, dr3 = st.columns(3)
            g_max_fo   = dr1.number_input("Max fanout",        value=20,   step=1)
            g_max_tr   = dr2.number_input("Max transition (ns)", value=0.2, step=0.01, format="%.3f")
            g_max_cap  = dr3.number_input("Max cap (pF)",       value=0.1,  step=0.01, format="%.3f")
            dr4, dr5 = st.columns(2)
            g_min_cap_en = dr4.checkbox("Min cap constraint")
            g_min_cap    = dr4.number_input("Min cap (pF)", value=0.01, step=0.001, format="%.4f") if g_min_cap_en else None
            g_max_area_en = dr5.checkbox("Max area constraint")
            g_max_area    = dr5.number_input("Max area", value=0.0, step=1.0, format="%.1f") if g_max_area_en else None

        # ── Operating conditions ─────────────────────────────────────────────
        with st.expander("🌡 Operating conditions"):
            g_add_oper = st.checkbox("Add set_operating_conditions")
            g_oper_name = st.text_input("Corner name (e.g. WORST, BEST, TYP)", value="WORST") if g_add_oper else "WORST"

        # ── Timing derate ─────────────────────────────────────────────────────
        with st.expander("📉 Timing derate — AOCV"):
            st.info("-late raises setup barrier · -early lowers hold barrier")
            g_add_derate = st.checkbox("Add set_timing_derate")
            if g_add_derate:
                d1, d2, d3, d4 = st.columns(4)
                g_dc_late  = d1.number_input("-late cell",   value=0.92, step=0.01, format="%.3f")
                g_dc_early = d2.number_input("-early cell",  value=1.08, step=0.01, format="%.3f")
                g_dn_late  = d3.number_input("-late net",    value=1.0,  step=0.01, format="%.3f")
                g_dn_early = d4.number_input("-early net",   value=1.0,  step=0.01, format="%.3f")
            else:
                g_dc_late, g_dc_early, g_dn_late, g_dn_early = 0.92, 1.08, 1.0, 1.0

        # ── Ideal networks & DFT ─────────────────────────────────────────────
        with st.expander("🧪 Ideal networks & DFT"):
            dft1, dft2 = st.columns(2)
            g_add_rst  = dft1.checkbox("Reset — ideal + false path", value=True)
            g_rst_port = dft1.text_input("Reset port", value="rst_n") if g_add_rst else "rst_n"
            g_add_scan = dft2.checkbox("Scan enable — case analysis + ideal")
            g_scan_port = dft2.text_input("Scan port", value="scan_en") if g_add_scan else "scan_en"

            g_add_pulse = st.checkbox("Min pulse width")
            g_pulse_val = st.number_input("Pulse (ns)", value=0.5, step=0.1, format="%.2f") if g_add_pulse else 0.5

            st.markdown("**set_case_analysis entries**")
            n_ca = st.number_input("Number of entries", min_value=0, max_value=10, value=0, step=1, key="nca")
            g_case_entries = []
            for i in range(int(n_ca)):
                ca1, ca2, ca3 = st.columns(3)
                ca_tgt  = ca1.text_input("Port/pin", key=f"cat{i}", placeholder="scan_en")
                ca_val  = ca2.selectbox("Value", ["0","1","rising","falling"], key=f"cav{i}")
                ca_type = ca3.selectbox("Type", ["port","pin"], key=f"catp{i}")
                if ca_tgt:
                    g_case_entries.append(CaseAnalysisEntry(target=ca_tgt, value=ca_val, obj_type=ca_type))

        # ── Disable timing arcs ──────────────────────────────────────────────
        with st.expander("🚫 Disable timing arcs"):
            st.warning("Only disable arcs that are physically non-functional. Always specify -from and -to pins.")
            n_da = st.number_input("Number of arcs", min_value=0, max_value=10, value=0, step=1, key="nda")
            g_disable_arcs = []
            for i in range(int(n_da)):
                da1, da2, da3 = st.columns(3)
                da_cell = da1.text_input("Cell", key=f"dac{i}", placeholder="U_MUX")
                da_from = da2.text_input("-from pin", key=f"daf{i}", placeholder="S0")
                da_to   = da3.text_input("-to pin",   key=f"dat{i}", placeholder="Z")
                if da_cell and da_from and da_to:
                    g_disable_arcs.append(DisableArc(cell=da_cell, from_pin=da_from, to_pin=da_to))

        # ── Timing exceptions ────────────────────────────────────────────────
        with st.expander("⏱ Timing exceptions"):
            st.markdown("**False paths**")
            n_fp = st.number_input("Number of false paths", min_value=0, max_value=20, value=0, step=1, key="nfp")
            g_false_paths = []
            for i in range(int(n_fp)):
                fp1, fp2 = st.columns(2)
                fp_from = fp1.text_input("From", key=f"fpf{i}", placeholder="rst_n")
                fp_to   = fp2.text_input("To",   key=f"fpt{i}", placeholder="FF_OUT/D")
                if fp_from and fp_to:
                    g_false_paths.append(FalsePath(from_obj=fp_from, to_obj=fp_to))

            st.markdown("**Multicycle paths** (-hold auto-added)")
            n_mc = st.number_input("Number of multicycle paths", min_value=0, max_value=20, value=0, step=1, key="nmc")
            g_mc_paths = []
            for i in range(int(n_mc)):
                mc1, mc2, mc3 = st.columns(3)
                mc_from   = mc1.text_input("From cell", key=f"mcf{i}", placeholder="U_REG_A")
                mc_to     = mc2.text_input("To cell",   key=f"mct{i}", placeholder="U_REG_B")
                mc_cycles = mc3.number_input("Cycles", value=2, min_value=2, step=1, key=f"mcc{i}")
                if mc_from and mc_to:
                    g_mc_paths.append(MultiCyclePath(from_cell=mc_from, to_cell=mc_to, cycles=mc_cycles))

            st.markdown("**Half-cycle paths** (rise↔fall, budget = period/2)")
            st.info("Requires paired -hold 0 — generated automatically.")
            n_hp = st.number_input("Number of half-cycle paths", min_value=0, max_value=8, value=0, step=1, key="nhp")
            g_half_paths = []
            for i in range(int(n_hp)):
                hp1, hp2 = st.columns(2)
                hp_clk = hp1.text_input("Clock name", key=f"hpc{i}", placeholder="clk_core")
                hp_dir = hp2.selectbox("Direction", [
                    "rise_to_fall", "fall_to_rise", "both"
                ], key=f"hpd{i}")
                if hp_clk:
                    g_half_paths.append(HalfCyclePath(clock=hp_clk, direction=hp_dir))

        # ── Power ─────────────────────────────────────────────────────────────
        with st.expander("⚡ Power constraints"):
            g_add_power = st.checkbox("Add power constraints")
            if g_add_power:
                pw1, pw2 = st.columns(2)
                g_dyn_pow  = pw1.number_input("Max dynamic power (mW)", value=100.0, step=1.0)
                g_leak_pow = pw2.number_input("Max leakage power (uW)",  value=10.0,  step=1.0)
            else:
                g_dyn_pow, g_leak_pow = 100.0, 10.0

        # ── Dont-use ──────────────────────────────────────────────────────────
        with st.expander("🚷 Dont-use cells"):
            du_raw = st.text_area(
                "Cell patterns (one per line)",
                placeholder="CLKBUF_X1\nINVD0\nBUFD1",
                height=80,
            )
            g_dont_use = [line.strip() for line in du_raw.splitlines() if line.strip()]

    # ── Build params and generate ─────────────────────────────────────────────
    params = SDCParams(
        design_name     = g_design,
        sdc_version     = g_sdc_ver,
        add_units       = g_units,
        time_unit       = g_time_u,
        cap_unit        = g_cap_u,
        res_unit        = g_res_u,
        clocks          = g_clocks or [ClockDef(name="clk_core", port="clk", period=5.0)],
        add_clk_jitter  = g_add_jitter,
        clk_jitter_val  = g_jitter_val,
        add_clk_transition = g_add_trans,
        clk_transition_val = g_trans_val,
        add_clk_gating  = g_add_gate,
        clk_gate_setup  = g_gate_setup,
        clk_gate_hold   = g_gate_hold,
        add_latency     = g_add_lat,
        latency_val     = g_lat_val,
        add_propagated  = g_add_prop,
        in_delay_max    = g_in_max,
        in_delay_min    = g_in_min,
        out_delay_max   = g_out_max,
        out_delay_min   = g_out_min,
        add_drive_cell  = g_add_drive and not g_add_intrans,
        drive_cell_name = g_drive_cell,
        add_input_transition = g_add_intrans and not g_add_drive,
        input_transition_val = g_intrans_val,
        add_load        = g_add_load,
        load_val        = g_load_val,
        max_fanout      = int(g_max_fo),
        max_transition  = g_max_tr,
        max_cap         = g_max_cap,
        min_cap         = g_min_cap,
        max_area        = g_max_area,
        add_oper_cond   = g_add_oper,
        oper_cond_name  = g_oper_name,
        add_derate      = g_add_derate,
        derate_cell_late  = g_dc_late,
        derate_cell_early = g_dc_early,
        derate_net_late   = g_dn_late,
        derate_net_early  = g_dn_early,
        add_ideal_rst   = g_add_rst,
        rst_port        = g_rst_port,
        add_scan        = g_add_scan,
        scan_port       = g_scan_port,
        add_min_pulse   = g_add_pulse,
        min_pulse_val   = g_pulse_val,
        case_entries    = g_case_entries,
        disable_arcs    = g_disable_arcs,
        false_paths     = g_false_paths,
        mc_paths        = g_mc_paths,
        half_paths      = g_half_paths,
        add_power       = g_add_power,
        max_dyn_power   = g_dyn_pow,
        max_leak_power  = g_leak_pow,
        dont_use        = g_dont_use,
    )

    sdc_output = generate_sdc(params)
    lines = sdc_output.count("\n") + 1

    with right:
        st.markdown(f"### 📄 `{g_design}.sdc` &nbsp; <span style='font-size:13px;color:#6b7280;font-weight:400'>{lines} lines · SDC v{g_sdc_ver}</span>", unsafe_allow_html=True)
        st.code(sdc_output, language="tcl")

        # ── NATIVE STREAMLIT DOWNLOAD — always works ───────────────────────
        st.download_button(
            label="⬇️ Download .sdc",
            data=sdc_output,
            file_name=f"{g_design or 'design'}.sdc",
            mime="text/plain",
            use_container_width=True,
            type="primary",
        )
        st.caption("File is ready to use — review all values before running synthesis.")

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 1: LIVE SDC VALIDATION (inside Generator tab)
    # ════════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("🛡 Live SDC Validation")

    with st.spinner("Running SDC checker..."):
        gen_check = check_sdc(sdc_output)

    gen_errors   = gen_check.errors
    gen_warnings = gen_check.warnings
    gen_info     = gen_check.info

    chk1, chk2, chk3, chk4 = st.columns(4)
    chk1.metric("❌ Errors",   len(gen_errors))
    chk2.metric("⚠️ Warnings", len(gen_warnings))
    chk3.metric("ℹ️ Info",     len(gen_info))
    chk4.metric("🕐 Clocks",   gen_check.stats.get("Clocks", 0))

    if gen_errors:
        st.error(f"**{len(gen_errors)} error{'s' if len(gen_errors)!=1 else ''}** found in generated SDC — review before synthesis.")
    elif gen_warnings:
        st.warning(f"No errors, but **{len(gen_warnings)} warning{'s' if len(gen_warnings)!=1 else ''}** need review.")
    else:
        st.success("✅ Generated SDC passed all checks — no errors or warnings.")

    if gen_errors or gen_warnings:
        with st.expander(f"View issues ({len(gen_errors)} errors, {len(gen_warnings)} warnings)"):
            for issue in gen_check.issues:
                icon = "🔴" if issue.sev == "error" else "🟡"
                st.markdown(f"{icon} **`{issue.code}`** — {issue.msg}")
    if gen_info:
        with st.expander(f"Best practice suggestions ({len(gen_info)})"):
            for item in gen_info:
                st.markdown(f"ℹ️ **`{item.code}`** — {item.msg}")

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 2: QUICK MULTI-CORNER GENERATE (inside Generator tab)
    # ════════════════════════════════════════════════════════════════════════
    if st.session_state.corners:
        st.divider()
        st.subheader("🔲 Quick Multi-Corner Generate")
        st.caption(
            f"Generate per-corner SDCs from this template using your {len(st.session_state.corners)} defined corners. "
            "Corners are managed in the **MMC Corner Manager** tab."
        )

        qc_names = [c.name for c in st.session_state.corners]
        qc_selected = st.multiselect(
            "Select corners to generate",
            qc_names,
            default=qc_names,
            key="qc_sel_corners",
        )
        qc_corners = [c for c in st.session_state.corners if c.name in qc_selected]

        if st.button("⚡ Generate All Corner SDCs", type="primary", use_container_width=True, key="qc_gen_btn"):
            with st.spinner(f"Generating SDCs for {len(qc_corners)} corners..."):
                st.session_state.generated_sdcs = generate_corner_sdcs(params, qc_corners)
            st.success(f"Generated {len(st.session_state.generated_sdcs)} corner SDCs.")

        # Show results if available
        if st.session_state.generated_sdcs:
            qc_gen = st.session_state.generated_sdcs
            qc_gen_names = list(qc_gen.keys())

            # Download buttons row
            dl1, dl2, dl3 = st.columns(3)
            with dl1:
                zip_bytes = create_corner_zip(qc_gen)
                st.download_button(
                    "📦 Download All (.zip)",
                    data=zip_bytes,
                    file_name="corner_sdcs.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                    key="qc_zip_dl",
                )
            with dl2:
                qc_dl_sel = st.selectbox("Download single corner", qc_gen_names, key="qc_dl_single")
                if qc_dl_sel:
                    st.download_button(
                        f"⬇️ {qc_dl_sel}.sdc",
                        data=qc_gen[qc_dl_sel],
                        file_name=f"{qc_dl_sel}.sdc",
                        mime="text/plain",
                        use_container_width=True,
                        key="qc_single_dl",
                    )
            with dl3:
                st.metric("Generated", len(qc_gen))

            # Per-corner SDC previews
            with st.expander(f"📄 Per-corner SDC previews ({len(qc_gen)} files)"):
                for corner_name, sdc_text in qc_gen.items():
                    with st.expander(f"📄 {corner_name}.sdc", expanded=False):
                        st.code(sdc_text, language="tcl")

            # Cross-corner consistency checks
            st.markdown("**🔗 Cross-Corner Consistency**")
            with st.spinner("Running cross-corner checks..."):
                qc_multi = check_sdc_multi(qc_gen)

            qc_m1, qc_m2, qc_m3 = st.columns(3)
            qc_m1.metric("❌ Errors",   len(qc_multi.errors))
            qc_m2.metric("⚠️ Warnings", len(qc_multi.warnings))
            qc_m3.metric("ℹ️ Info",     len(qc_multi.info))

            if qc_multi.errors:
                st.error(f"**{len(qc_multi.errors)} error{'s' if len(qc_multi.errors)!=1 else ''}** across corners.")
            elif qc_multi.warnings:
                st.warning(f"**{len(qc_multi.warnings)} warning{'s' if len(qc_multi.warnings)!=1 else ''}** across corners.")
            else:
                st.success("✅ Cross-corner consistency checks passed.")

            if qc_multi.issues:
                with st.expander(f"Cross-corner issues ({len(qc_multi.issues)})"):
                    for issue in qc_multi.issues:
                        icon = "🔴" if issue.sev == "error" else "🟡"
                        st.markdown(f"{icon} **`{issue.code}`** — {issue.msg}")

            if qc_multi.info:
                with st.expander(f"Cross-corner info ({len(qc_multi.info)})"):
                    for item in qc_multi.info:
                        st.markdown(f"ℹ️ **`{item.code}`** — {item.msg}")

            # Corner diff
            if len(qc_gen_names) >= 2:
                st.markdown("**🔍 Corner Diff**")
                qc_d1, qc_d2 = st.columns(2)
                with qc_d1:
                    qc_diff_a = st.selectbox("Corner A", qc_gen_names, index=0, key="qc_diff_a")
                with qc_d2:
                    qc_diff_b = st.selectbox("Corner B", qc_gen_names, index=min(1, len(qc_gen_names)-1), key="qc_diff_b")

                if qc_diff_a != qc_diff_b:
                    qc_diff_result = diff_corners(qc_gen[qc_diff_a], qc_gen[qc_diff_b], qc_diff_a, qc_diff_b)
                    n_diff = sum(1 for d in qc_diff_result if d.line_type != "equal")
                    st.caption(f"{n_diff} different lines between **{qc_diff_a}** and **{qc_diff_b}**")
                    if n_diff > 0:
                        diff_html = []
                        for d in qc_diff_result:
                            if d.line_type == "equal":
                                continue
                            elif d.line_type == "added":
                                diff_html.append(f'<div style="background:#E6FFE6;padding:2px 8px;font-family:monospace;font-size:12px;border-left:3px solid #22c55e;margin:1px 0"><b>+ {qc_diff_b}:</b> {d.text_b}</div>')
                            elif d.line_type == "removed":
                                diff_html.append(f'<div style="background:#FFE6E6;padding:2px 8px;font-family:monospace;font-size:12px;border-left:3px solid #ef4444;margin:1px 0"><b>- {qc_diff_a}:</b> {d.text_a}</div>')
                            elif d.line_type == "changed":
                                diff_html.append(f'<div style="background:#FFF8E1;padding:2px 8px;font-family:monospace;font-size:12px;border-left:3px solid #eab308;margin:1px 0"><b>~ {qc_diff_a}:</b> {d.text_a}</div>')
                                diff_html.append(f'<div style="background:#FFF8E1;padding:2px 8px;font-family:monospace;font-size:12px;border-left:3px solid #3b82f6;margin:1px 0"><b>~ {qc_diff_b}:</b> {d.text_b}</div>')
                        st.markdown("".join(diff_html), unsafe_allow_html=True)
                    else:
                        st.success("No differences between these corners.")
    else:
        st.divider()
        st.info("🔲 **Multi-Corner Generate** — Define corners in the **MMC Corner Manager** tab to generate per-corner SDCs from this template.")

    # ════════════════════════════════════════════════════════════════════════
    # SECTION 3: COMPARE AGAINST BASELINE (inside Generator tab)
    # ════════════════════════════════════════════════════════════════════════
    st.divider()
    st.subheader("🔍 Compare Against Baseline")
    st.caption("Upload an existing SDC to compare against your newly generated version — detects hidden changes that a text diff would miss.")

    bc_up, bc_paste = st.columns(2)
    with bc_up:
        baseline_file = st.file_uploader("Upload baseline .sdc", type=["sdc", "tcl", "txt"], key="gen_baseline_up")
    with bc_paste:
        baseline_text = st.text_area(
            "Or paste baseline SDC",
            height=80,
            placeholder="Paste an existing SDC to compare against...",
            key="gen_baseline_paste",
        )

    baseline_sdc = None
    if baseline_file:
        baseline_sdc = baseline_file.read().decode("utf-8", errors="replace")
    elif baseline_text.strip():
        baseline_sdc = baseline_text

    if st.button("🔍 Compare with Baseline", type="primary", use_container_width=True, key="gen_compare_btn"):
        if not baseline_sdc:
            st.warning("Provide a baseline SDC (upload or paste) to compare against.")
        else:
            with st.spinner("Analyzing constraint changes..."):
                gen_cmp_result = analyze_constraint_changes(baseline_sdc, sdc_output)

            gen_cmp_stats = gen_cmp_result.stats
            gcs1, gcs2, gcs3, gcs4 = st.columns(4)
            gcs1.metric("🔴 Fatal",     gen_cmp_stats.get("fatal", 0))
            gcs2.metric("🟡 Warnings",   gen_cmp_stats.get("warnings", 0))
            gcs3.metric("ℹ️ Info",       gen_cmp_stats.get("info", 0))
            gcs4.metric("Total changes", gen_cmp_stats.get("total_changes", 0))

            if not gen_cmp_result.changes:
                st.success("✅ Generated SDC is identical to baseline (no constraint changes detected).")
            else:
                # Fatal changes
                if gen_cmp_result.fatal_changes:
                    st.error(f"**{len(gen_cmp_result.fatal_changes)} fatal change{'s' if len(gen_cmp_result.fatal_changes)!=1 else ''}** detected.")
                    for c in gen_cmp_result.fatal_changes:
                        with st.expander(f"🔴 `{c.rule.rule_id}` — {c.explanation[:80]}..."):
                            st.markdown(f'<span class="fatal-badge">Fatal</span>', unsafe_allow_html=True)
                            st.markdown(f"**{c.rule.description}**")
                            if c.v1_text:
                                st.markdown(f"**Baseline:** `{c.v1_text}`")
                            if c.v2_text:
                                st.markdown(f"**Generated:** `{c.v2_text}`")
                            st.markdown(f"**Impact:** {c.explanation}")

                # Warning changes
                if gen_cmp_result.warnings:
                    for c in gen_cmp_result.warnings:
                        with st.expander(f"🟡 `{c.rule.rule_id}` — {c.explanation[:80]}..."):
                            st.markdown(f'<span class="warn-badge">Warning</span>', unsafe_allow_html=True)
                            st.markdown(f"**{c.rule.description}**")
                            if c.v1_text:
                                st.markdown(f"**Baseline:** `{c.v1_text}`")
                            if c.v2_text:
                                st.markdown(f"**Generated:** `{c.v2_text}`")
                            st.markdown(f"**Impact:** {c.explanation}")

                # Info changes
                if gen_cmp_result.info_changes:
                    for c in gen_cmp_result.info_changes:
                        with st.expander(f"ℹ️ `{c.rule.rule_id}` — {c.explanation[:80]}..."):
                            st.markdown(f'<span class="info-badge">Info</span>', unsafe_allow_html=True)
                            st.markdown(f"**{c.rule.description}**")
                            if c.v1_text:
                                st.markdown(f"**Baseline:** `{c.v1_text}`")
                            if c.v2_text:
                                st.markdown(f"**Generated:** `{c.v2_text}`")
                            st.markdown(f"**Impact:** {c.explanation}")

                # Text diff
                with st.expander("📄 Side-by-side Text Diff"):
                    diff_lines = list(difflib.unified_diff(
                        baseline_sdc.splitlines(),
                        sdc_output.splitlines(),
                        fromfile="Baseline",
                        tofile="Generated",
                        lineterm="",
                    ))
                    if diff_lines:
                        diff_html = []
                        for line in diff_lines:
                            if line.startswith("+"):
                                diff_html.append(f'<div style="background:#E6FFE6;padding:2px 8px;font-family:monospace;font-size:12px">{line}</div>')
                            elif line.startswith("-"):
                                diff_html.append(f'<div style="background:#FFE6E6;padding:2px 8px;font-family:monospace;font-size:12px">{line}</div>')
                            elif line.startswith("@@"):
                                diff_html.append(f'<div style="background:#E6F1FB;padding:2px 8px;font-family:monospace;font-size:12px;font-weight:600">{line}</div>')
                            else:
                                diff_html.append(f'<div style="padding:2px 8px;font-family:monospace;font-size:12px;color:#6b7280">{line}</div>')
                        st.markdown("".join(diff_html), unsafe_allow_html=True)
                    else:
                        st.info("No text differences found.")


# ════════════════════════════════════════════════════════════════════════════
# MMC CORNER MANAGER TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_mmc_mgr:
    st.subheader("🔲 MMC Corner Manager")
    st.caption("Define PVT timing corners for multi-corner SDC generation")

    # ── Preset selector + import/export ────────────────────────────────────
    mgr_row1 = st.columns([2, 1, 1])
    with mgr_row1[0]:
        preset_name = st.selectbox(
            "Load corner preset",
            list(CORNER_PRESETS.keys()),
            index=0,
            key="preset_select",
        )
    with mgr_row1[1]:
        if st.button("📥 Load Preset", use_container_width=True):
            st.session_state.corners = [Corner(**corner_to_dict(c)) for c in CORNER_PRESETS[preset_name]]
            st.session_state.generated_sdcs = {}
            st.rerun()
    with mgr_row1[2]:
        if st.session_state.corners:
            json_data = corners_to_json(st.session_state.corners)
            st.download_button(
                "📤 Export JSON",
                data=json_data,
                file_name="corners.json",
                mime="application/json",
                use_container_width=True,
            )

    # ── Import JSON ────────────────────────────────────────────────────────
    with st.expander("📥 Import corners from JSON file"):
        imported_file = st.file_uploader("Upload corners JSON", type=["json"], key="import_corners")
        if imported_file:
            try:
                text = imported_file.read().decode("utf-8")
                imported_corners = corners_from_json(text)
                st.session_state.corners = imported_corners
                st.success(f"Imported {len(imported_corners)} corners.")
                st.rerun()
            except Exception as e:
                st.error(f"Import failed: {e}")

    st.divider()

    # ── Main layout: Corner list + Add/Edit form ───────────────────────────
    col_list, col_form = st.columns([3, 2])

    with col_form:
        st.markdown("**➕ Add / Edit Corner**")

        editing = st.session_state.editing_corner_idx is not None
        edit_c = st.session_state.corners[st.session_state.editing_corner_idx] if editing else None

        fc_name  = st.text_input("Corner name", value=edit_c.name if edit_c else "", key="fc_name")
        fc_proc  = st.selectbox("Process type", ["SSG", "TT", "FFG", "SS", "FF", "SF", "FS"],
                                index=["SSG", "TT", "FFG", "SS", "FF", "SF", "FS"].index(edit_c.process_type) if edit_c else 0,
                                key="fc_proc")
        fc_v     = st.number_input("Voltage (V)", value=edit_c.voltage if edit_c else 0.72,
                                   min_value=0.01, max_value=2.0, step=0.01, format="%.3f", key="fc_v")
        fc_t     = st.number_input("Temperature (°C)", value=edit_c.temperature if edit_c else -40.0,
                                   min_value=-55.0, max_value=175.0, step=1.0, format="%.0f", key="fc_t")
        fc_opc   = st.text_input("Operating condition", value=edit_c.operating_condition if edit_c else "",
                                 placeholder="e.g. SSG_0P72V_M40C", key="fc_opc")

        dc1, dc2 = st.columns(2)
        fc_de    = dc1.number_input("Cell early", value=edit_c.derate_cell_early if edit_c else 1.08,
                                    min_value=0.5, max_value=1.5, step=0.01, format="%.3f", key="fc_de")
        fc_dl    = dc2.number_input("Cell late", value=edit_c.derate_cell_late if edit_c else 0.92,
                                    min_value=0.5, max_value=1.5, step=0.01, format="%.3f", key="fc_dl")
        dc3, dc4 = st.columns(2)
        fc_ne    = dc3.number_input("Net early", value=edit_c.derate_net_early if edit_c else 1.0,
                                    min_value=0.5, max_value=1.5, step=0.01, format="%.3f", key="fc_ne")
        fc_nl    = dc4.number_input("Net late", value=edit_c.derate_net_late if edit_c else 1.0,
                                    min_value=0.5, max_value=1.5, step=0.01, format="%.3f", key="fc_nl")
        fc_us    = st.number_input("Uncertainty scale", value=edit_c.uncertainty_scale if edit_c else 1.0,
                                   min_value=0.1, max_value=3.0, step=0.1, format="%.2f", key="fc_us")

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            btn_label = "✅ Update Corner" if editing else "➕ Add Corner"
            if st.button(btn_label, use_container_width=True, type="primary"):
                new_corner = Corner(
                    name=fc_name.strip(),
                    operating_condition=fc_opc.strip(),
                    voltage=fc_v,
                    temperature=fc_t,
                    process_type=fc_proc,
                    derate_cell_early=fc_de,
                    derate_cell_late=fc_dl,
                    derate_net_early=fc_ne,
                    derate_net_late=fc_nl,
                    uncertainty_scale=fc_us,
                )
                errors = validate_corner(new_corner)
                if errors:
                    for e in errors:
                        st.warning(e)
                elif not fc_name.strip():
                    st.warning("Corner name is required.")
                else:
                    if editing:
                        st.session_state.corners[st.session_state.editing_corner_idx] = new_corner
                        st.session_state.editing_corner_idx = None
                    else:
                        # Check duplicate name
                        existing_names = [c.name for c in st.session_state.corners]
                        if fc_name.strip() in existing_names:
                            st.warning(f'Corner "{fc_name.strip()}" already exists.')
                        else:
                            st.session_state.corners.append(new_corner)
                    st.session_state.generated_sdcs = {}
                    st.rerun()
        with btn_col2:
            if editing:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.editing_corner_idx = None
                    st.rerun()

    with col_list:
        if not st.session_state.corners:
            st.info("No corners defined yet. Load a preset or add corners manually.")
        else:
            st.markdown(f"**{len(st.session_state.corners)} corners defined**")

            for idx, c in enumerate(st.session_state.corners):
                with st.expander(f"🔲 {c.name}", expanded=False):
                    info_md = (
                        f"**Process:** {c.process_type}  |  "
                        f"**Voltage:** {c.voltage:.2f}V  |  "
                        f"**Temp:** {c.temperature:.0f}°C  \n"
                        f"**Cell early:** {c.derate_cell_early:.3f}  |  "
                        f"**Cell late:** {c.derate_cell_late:.3f}  |  "
                        f"**Net early:** {c.derate_net_early:.3f}  |  "
                        f"**Net late:** {c.derate_net_late:.3f}  \n"
                        f"**Uncertainty scale:** {c.uncertainty_scale:.2f}x  |  "
                        f"**Op condition:** {c.operating_condition or '(none)'}"
                    )
                    st.markdown(info_md)
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        if st.button("✏️ Edit", key=f"edit_{idx}", use_container_width=True):
                            st.session_state.editing_corner_idx = idx
                            st.rerun()
                    with ec2:
                        if st.button("🗑 Delete", key=f"del_{idx}", use_container_width=True):
                            st.session_state.corners.pop(idx)
                            st.session_state.generated_sdcs = {}
                            st.rerun()

    # ── Corner Coverage Matrix ─────────────────────────────────────────────
    if st.session_state.corners:
        st.divider()
        st.subheader("📊 Corner Coverage Matrix")
        matrix = corner_matrix(st.session_state.corners)
        import pandas as pd
        df = pd.DataFrame(matrix).T
        st.dataframe(df, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# MMC SDC GENERATOR TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_mmc_gen:
    st.subheader("📦 Multi-Corner SDC Generator")
    st.caption("Generate per-corner SDC files from a base template — compare, validate, and download")

    if not st.session_state.corners:
        st.warning("⚠️ No corners defined. Go to the **MMC Corner Manager** tab first.")
    else:
        st.info(f"📍 {len(st.session_state.corners)} corners available: {', '.join(c.name for c in st.session_state.corners)}")

        # ── Base template (simplified) ─────────────────────────────────────
        with st.expander("📝 Base SDC Template Configuration", expanded=True):
            mt_col1, mt_col2 = st.columns(2)
            with mt_col1:
                mg_design = st.text_input("Design name", value="MY_DESIGN", key="mmc_design")
                mg_sdc_ver = st.selectbox("SDC version", ["2.2", "2.1", "2.0"], index=0, key="mmc_sdc_ver")
            with mt_col2:
                mg_units = st.checkbox("Add set_units", value=True, key="mmc_units")
                if mg_units:
                    uc1, uc2 = st.columns(2)
                    mg_time_u = uc1.selectbox("Time unit", ["ns", "ps"], index=0, key="mmc_tu")
                    mg_cap_u  = uc2.selectbox("Cap unit",  ["pF", "fF"], index=0, key="mmc_cu")
                else:
                    mg_time_u, mg_cap_u = "ns", "pF"

            st.markdown("**Clocks**")
            mg_n_clocks = st.number_input("Number of clocks", min_value=1, max_value=4, value=1, step=1, key="mmc_nclk")
            mg_clocks = []
            for i in range(int(mg_n_clocks)):
                mc1, mc2, mc3 = st.columns(3)
                clk_name = mc1.text_input("Name", value=f"clk_{'core' if i==0 else f'div{i}'}", key=f"mmc_cn{i}")
                clk_port = mc2.text_input("Port", value="clk" if i==0 else f"clk{i}", key=f"mmc_cp{i}")
                clk_per  = mc3.number_input("Period (ns)", value=5.0 if i==0 else 10.0, step=0.1, format="%.3f", key=f"mmc_cper{i}")
                clk_unc  = st.number_input("Uncertainty (ns)", value=0.15, step=0.01, format="%.3f", key=f"mmc_cunc{i}")
                mg_clocks.append(ClockDef(name=clk_name, port=clk_port, period=clk_per, uncertainty=clk_unc))

            st.markdown("**I/O & Design Rules**")
            io_r1, io_r2 = st.columns(2)
            mg_in_max  = io_r1.number_input("Input delay -max", value=1.2, step=0.1, format="%.2f", key="mmc_inmax")
            mg_in_min  = io_r2.number_input("Input delay -min", value=0.4, step=0.1, format="%.2f", key="mmc_inmin")
            mg_out_max = io_r1.number_input("Output delay -max", value=1.5, step=0.1, format="%.2f", key="mmc_outmax")
            mg_out_min = io_r2.number_input("Output delay -min", value=0.5, step=0.1, format="%.2f", key="mmc_outmin")
            dr_r1, dr_r2, dr_r3 = st.columns(3)
            mg_max_fo  = dr_r1.number_input("Max fanout", value=20, step=1, key="mmc_fo")
            mg_max_tr  = dr_r2.number_input("Max transition", value=0.2, step=0.01, format="%.3f", key="mmc_tr")
            mg_max_cap = dr_r3.number_input("Max cap (pF)", value=0.1, step=0.01, format="%.3f", key="mmc_cap")

            st.markdown("**Ideal / DFT**")
            mg_rst = st.checkbox("Reset false path + ideal", value=True, key="mmc_rst")
            mg_rst_port = st.text_input("Reset port", value="rst_n", key="mmc_rstport") if mg_rst else "rst_n"
            mg_scan = st.checkbox("Scan enable case analysis", value=False, key="mmc_scan")
            mg_scan_port = st.text_input("Scan port", value="scan_en", key="mmc_scanport") if mg_scan else "scan_en"

        # ── Corner selection ────────────────────────────────────────────────
        corner_names = [c.name for c in st.session_state.corners]
        selected_corners_names = st.multiselect(
            "Select corners to generate",
            corner_names,
            default=corner_names,
            key="mmc_sel_corners",
        )
        selected_corners = [c for c in st.session_state.corners if c.name in selected_corners_names]

        if st.button("⚡ Generate All Corner SDCs", type="primary", use_container_width=True):
            base_params = SDCParams(
                design_name=mg_design,
                sdc_version=mg_sdc_ver,
                add_units=mg_units,
                time_unit=mg_time_u,
                cap_unit=mg_cap_u,
                res_unit="kOhm",
                clocks=mg_clocks or [ClockDef(name="clk_core", port="clk", period=5.0)],
                in_delay_max=mg_in_max,
                in_delay_min=mg_in_min,
                out_delay_max=mg_out_max,
                out_delay_min=mg_out_min,
                max_fanout=int(mg_max_fo),
                max_transition=mg_max_tr,
                max_cap=mg_max_cap,
                add_ideal_rst=mg_rst,
                rst_port=mg_rst_port,
                add_scan=mg_scan,
                scan_port=mg_scan_port,
            )
            with st.spinner(f"Generating SDCs for {len(selected_corners)} corners..."):
                st.session_state.generated_sdcs = generate_corner_sdcs(base_params, selected_corners)
            st.success(f"Generated {len(st.session_state.generated_sdcs)} corner SDCs.")

        # ── Results ────────────────────────────────────────────────────────
        if st.session_state.generated_sdcs:
            st.divider()
            gen = st.session_state.generated_sdcs
            gen_names = list(gen.keys())

            # Download buttons
            dl_cols = st.columns(3)
            with dl_cols[0]:
                zip_bytes = create_corner_zip(gen)
                st.download_button(
                    "📦 Download All (.zip)",
                    data=zip_bytes,
                    file_name="corner_sdcs.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                )
            with dl_cols[1]:
                sel_dl = st.selectbox("Download single corner", gen_names, key="mmc_dl_single")
                if sel_dl:
                    st.download_button(
                        f"⬇️ {sel_dl}.sdc",
                        data=gen[sel_dl],
                        file_name=f"{sel_dl}.sdc",
                        mime="text/plain",
                        use_container_width=True,
                    )
            with dl_cols[2]:
                st.metric("Generated", len(gen))

            # ── Corner Diff View ───────────────────────────────────────────
            st.subheader("🔍 Corner Diff")
            if len(gen_names) >= 2:
                diff_c1, diff_c2 = st.columns(2)
                with diff_c1:
                    diff_a = st.selectbox("Corner A", gen_names, index=0, key="diff_a")
                with diff_c2:
                    diff_b = st.selectbox("Corner B", gen_names, index=min(1, len(gen_names)-1), key="diff_b")

                if diff_a != diff_b:
                    diff_result = diff_corners(gen[diff_a], gen[diff_b], diff_a, diff_b)
                    n_equal = sum(1 for d in diff_result if d.line_type == "equal")
                    n_diff  = len(diff_result) - n_equal

                    diff_stats = st.columns(3)
                    diff_stats[0].metric("Equal lines", n_equal)
                    diff_stats[1].metric("Different lines", n_diff)
                    diff_stats[2].metric("Total", len(diff_result))

                    # Render diff
                    diff_html = []
                    for d in diff_result:
                        if d.line_type == "equal":
                            continue  # Skip identical lines for brevity
                        elif d.line_type == "added":
                            diff_html.append(f'<div style="background:#E6FFE6;padding:2px 8px;font-family:monospace;font-size:12px;border-left:3px solid #22c55e;margin:1px 0"><b>+ {diff_b}:</b> {d.text_b}</div>')
                        elif d.line_type == "removed":
                            diff_html.append(f'<div style="background:#FFE6E6;padding:2px 8px;font-family:monospace;font-size:12px;border-left:3px solid #ef4444;margin:1px 0"><b>- {diff_a}:</b> {d.text_a}</div>')
                        elif d.line_type == "changed":
                            diff_html.append(f'<div style="background:#FFF8E1;padding:2px 8px;font-family:monospace;font-size:12px;border-left:3px solid #eab308;margin:1px 0"><b>~ {diff_a}:</b> {d.text_a}</div>')
                            diff_html.append(f'<div style="background:#FFF8E1;padding:2px 8px;font-family:monospace;font-size:12px;border-left:3px solid #3b82f6;margin:1px 0"><b>~ {diff_b}:</b> {d.text_b}</div>')

                    if diff_html:
                        st.markdown("".join(diff_html), unsafe_allow_html=True)
                    else:
                        st.success("No differences found between the two corners (excluding expected corner-specific lines).")
                else:
                    st.info("Select two different corners to compare.")
            else:
                st.info("Need at least 2 generated corners to diff.")

            # ── Cross-Corner Consistency ────────────────────────────────────
            st.subheader("🔗 Cross-Corner Consistency")
            with st.spinner("Running cross-corner checks..."):
                multi_result = check_sdc_multi(gen)

            multi_errors   = multi_result.errors
            multi_warnings = multi_result.warnings

            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("❌ Errors", len(multi_errors))
            mc2.metric("⚠️ Warnings", len(multi_warnings))
            mc3.metric("ℹ️ Info", len(multi_result.info))

            if multi_errors:
                st.error(f"**{len(multi_errors)} error{'s' if len(multi_errors)!=1 else ''}** across corners.")
            elif multi_warnings:
                st.warning(f"**{len(multi_warnings)} warning{'s' if len(multi_warnings)!=1 else ''}** across corners.")
            else:
                st.success("✅ Cross-corner consistency checks passed.")

            if multi_result.issues:
                with st.expander(f"Issues ({len(multi_result.issues)})"):
                    for issue in multi_result.issues:
                        icon = "🔴" if issue.sev == "error" else "🟡"
                        st.markdown(f"{icon} **`{issue.code}`** — {issue.msg}")

            if multi_result.info:
                with st.expander(f"Info ({len(multi_result.info)})"):
                    for item in multi_result.info:
                        st.markdown(f"ℹ️ **`{item.code}`** — {item.msg}")

            # ── Per-corner SDC previews ─────────────────────────────────────
            st.subheader("📄 Generated SDCs")
            for corner_name, sdc_text in gen.items():
                with st.expander(f"📄 {corner_name}.sdc"):
                    st.code(sdc_text, language="tcl")


# ════════════════════════════════════════════════════════════════════════════
# CONSTRAINT CHANGE ANALYZER TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_analyzer:
    st.subheader("🔍 Constraint Change Analyzer")
    st.caption(
        "Upload two SDC versions to detect hidden changes that can cause thousands of violations — "
        "inspired by [Ausdia's analysis of variable indirection and cascade failures]"
        "(https://www.ausdia.com/blog/6/not-much-change-in-constraints-leads-to-thousands-of-violations/filter/0)."
    )

    # ── File upload section ────────────────────────────────────────────────
    col_v1, col_v2 = st.columns(2)

    with col_v1:
        st.markdown("**📄 Version 1 (V1)**")
        sdc_v1_uploaded = st.file_uploader("Upload V1 .sdc", type=["sdc", "tcl", "txt"], key="ca_v1_up")
        sdc_v1_pasted = st.text_area(
            "Or paste V1 text", height=120,
            placeholder="set sdc_version 2.2\ncreate_clock -name clk_core -period 5.0 [get_ports clk]\n...",
            key="ca_v1_paste",
        )
        sdc_v1 = None
        if sdc_v1_uploaded:
            sdc_v1 = sdc_v1_uploaded.read().decode("utf-8", errors="replace")
        elif sdc_v1_pasted.strip():
            sdc_v1 = sdc_v1_pasted

        st.markdown("**📎 V1 linked TCL files**")
        v1_linked = st.file_uploader(
            "Upload variable definition files (source *.tcl)",
            type=["tcl", "sdc", "txt"], accept_multiple_files=True,
            key="ca_v1_links",
        )

    with col_v2:
        st.markdown("**📄 Version 2 (V2)**")
        sdc_v2_uploaded = st.file_uploader("Upload V2 .sdc", type=["sdc", "tcl", "txt"], key="ca_v2_up")
        sdc_v2_pasted = st.text_area(
            "Or paste V2 text", height=120,
            placeholder="set sdc_version 2.2\ncreate_clock -name clk_core -period 5.0 [get_ports clk]\n...",
            key="ca_v2_paste",
        )
        sdc_v2 = None
        if sdc_v2_uploaded:
            sdc_v2 = sdc_v2_uploaded.read().decode("utf-8", errors="replace")
        elif sdc_v2_pasted.strip():
            sdc_v2 = sdc_v2_pasted

        st.markdown("**📎 V2 linked TCL files**")
        v2_linked = st.file_uploader(
            "Upload variable definition files (source *.tcl)",
            type=["tcl", "sdc", "txt"], accept_multiple_files=True,
            key="ca_v2_links",
        )

    # ── Analyze button ─────────────────────────────────────────────────────
    analyze_clicked = st.button("🔍 Analyze Changes", type="primary", use_container_width=True)

    if analyze_clicked:
        if not sdc_v1 or not sdc_v2:
            st.warning("Both V1 and V2 SDC text must be provided.")
        else:
            # Read linked files
            linked_v1: Dict[str, str] = {}
            if v1_linked:
                for f in v1_linked:
                    linked_v1[f.name] = f.read().decode("utf-8", errors="replace")
            linked_v2: Dict[str, str] = {}
            if v2_linked:
                for f in v2_linked:
                    linked_v2[f.name] = f.read().decode("utf-8", errors="replace")

            with st.spinner("Analyzing constraint changes..."):
                st.session_state.analyzer_result = analyze_constraint_changes(
                    sdc_v1, sdc_v2,
                    linked_files_v1=linked_v1 or None,
                    linked_files_v2=linked_v2 or None,
                )
            st.success("Analysis complete.")

    # ── Results display ────────────────────────────────────────────────────
    result = st.session_state.analyzer_result
    if result:
        st.divider()

        # ── Summary metrics ────────────────────────────────────────────────
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("🔴 Fatal", result.stats.get("fatal", 0))
        s2.metric("🟡 Warnings", result.stats.get("warnings", 0))
        s3.metric("ℹ️ Info", result.stats.get("info", 0))
        s4.metric("Total changes", result.stats.get("total_changes", 0))

        sev2, sev3 = st.columns(2)
        sev2.metric("📥 V1 constraints", result.stats.get("v1_constraints", 0))
        sev3.metric("📥 V2 constraints", result.stats.get("v2_constraints", 0))

        # ── Variable resolution info ────────────────────────────────────────
        if result.symbol_table_v1 or result.symbol_table_v2:
            with st.expander("📊 Variable Resolution View", expanded=False):
                v_col1, v_col2 = st.columns(2)
                if result.symbol_table_v1 and result.symbol_table_v1.variables:
                    with v_col1:
                        st.markdown(f"**V1 — {len(result.symbol_table_v1.variables)} variables**")
                        for name, binding in sorted(result.symbol_table_v1.variables.items()):
                            st.code(f"{name} = {binding.resolved_value}", language="tcl")
                if result.symbol_table_v2 and result.symbol_table_v2.variables:
                    with v_col2:
                        st.markdown(f"**V2 — {len(result.symbol_table_v2.variables)} variables**")
                        for name, binding in sorted(result.symbol_table_v2.variables.items()):
                            st.code(f"{name} = {binding.resolved_value}", language="tcl")

        if not result.changes:
            st.success("✅ No changes detected between V1 and V2.")
        else:
            # ── Fatal changes ──────────────────────────────────────────────
            fatals = result.fatal_changes
            if fatals:
                st.subheader(f"🔴 Fatal Changes ({len(fatals)})")
                st.error("These changes are likely to cause timing violations and require immediate attention.")
                for c in fatals:
                    with st.expander(f"🔴 `{c.rule.rule_id}` — {c.explanation[:80]}..."):
                        st.markdown(f'<span class="fatal-badge">Fatal</span>', unsafe_allow_html=True)
                        st.markdown(f"**{c.rule.description}**")
                        if c.v1_text:
                            st.markdown(f"**V1:** `{c.v1_text}`")
                        if c.v2_text:
                            st.markdown(f"**V2:** `{c.v2_text}`")
                        st.markdown(f"**Impact:** {c.explanation}")

            # ── Warnings ──────────────────────────────────────────────────
            warnings = result.warnings
            if warnings:
                st.subheader(f"🟡 Warnings ({len(warnings)})")
                for c in warnings:
                    with st.expander(f"🟡 `{c.rule.rule_id}` — {c.explanation[:80]}..."):
                        st.markdown(f'<span class="warn-badge">Warning</span>', unsafe_allow_html=True)
                        st.markdown(f"**{c.rule.description}**")
                        if c.v1_text:
                            st.markdown(f"**V1:** `{c.v1_text}`")
                        if c.v2_text:
                            st.markdown(f"**V2:** `{c.v2_text}`")
                        st.markdown(f"**Impact:** {c.explanation}")

            # ── Info changes ──────────────────────────────────────────────
            infos = result.info_changes
            if infos:
                st.subheader(f"ℹ️ Info ({len(infos)})")
                for c in infos:
                    with st.expander(f"ℹ️ `{c.rule.rule_id}` — {c.explanation[:80]}..."):
                        st.markdown(f'<span class="info-badge">Info</span>', unsafe_allow_html=True)
                        st.markdown(f"**{c.rule.description}**")
                        if c.v1_text:
                            st.markdown(f"**V1:** `{c.v1_text}`")
                        if c.v2_text:
                            st.markdown(f"**V2:** `{c.v2_text}`")
                        st.markdown(f"**Impact:** {c.explanation}")

            # ── Side-by-side text diff ────────────────────────────────────
            with st.expander("📄 Side-by-side Text Diff"):
                import difflib
                diff_lines = list(difflib.unified_diff(
                    sdc_v1.splitlines() if sdc_v1 else [],
                    sdc_v2.splitlines() if sdc_v2 else [],
                    fromfile="V1", tofile="V2",
                    lineterm="",
                ))
                if diff_lines:
                    diff_html = []
                    for line in diff_lines:
                        if line.startswith("+"):
                            diff_html.append(f'<div style="background:#E6FFE6;padding:2px 8px;font-family:monospace;font-size:12px">{line}</div>')
                        elif line.startswith("-"):
                            diff_html.append(f'<div style="background:#FFE6E6;padding:2px 8px;font-family:monospace;font-size:12px">{line}</div>')
                        elif line.startswith("@@"):
                            diff_html.append(f'<div style="background:#E6F1FB;padding:2px 8px;font-family:monospace;font-size:12px;font-weight:600">{line}</div>')
                        else:
                            diff_html.append(f'<div style="padding:2px 8px;font-family:monospace;font-size:12px;color:#6b7280">{line}</div>')
                    st.markdown("".join(diff_html), unsafe_allow_html=True)
                else:
                    st.info("No text-level differences (changes may be in linked variable files).")
    elif not analyze_clicked:
        st.info("Upload or paste two SDC versions and click **Analyze Changes** to see semantic differences.")


# ════════════════════════════════════════════════════════════════════════════
# CLOCK RELATIONS TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_clock_rel:
    st.subheader("🕐 Clock Relation Analyzer")
    st.caption(
        "Analyzes all clock pairs in your SDC, infers correct relationships, and detects mismatches "
        "in `set_clock_groups` constraints. Inspired by "
        "[Ausdia's Clock Relations Quiz](https://www.ausdia.com/blog/5/seemingly-simple-clock-relations-quiz/filter/0)."
    )

    cr_col_up, cr_col_paste = st.columns([1, 2])
    with cr_col_up:
        cr_uploaded = st.file_uploader("Upload .sdc / .tcl / .txt", type=["sdc", "tcl", "txt"], key="cr_upload")
    with cr_col_paste:
        cr_pasted = st.text_area(
            "Or paste SDC text here", height=120,
            placeholder=(
                "create_clock -name CLKA -period 1.00 [get_ports CLKAB]\n"
                "create_clock -name CLKB -period 1.50 [get_ports CLKAB] -add\n"
                "create_clock -name CLKC -period 2.30 [get_ports CLKC]\n"
                "create_generated_clock -name CLKA_DIV2 -divide_by 2 -master_clock CLKA ..."
            ),
            key="cr_paste",
        )

    cr_text = None
    if cr_uploaded:
        cr_text = cr_uploaded.read().decode("utf-8", errors="replace")
    elif cr_pasted.strip():
        cr_text = cr_pasted

    if cr_text and st.button("🔍 Analyze Clock Relations", type="primary", use_container_width=True, key="cr_analyze_btn"):
        with st.spinner("Analyzing clock relations..."):
            cr_result = clock_relations.analyze_clock_relations(cr_text)

        if not cr_result.clocks:
            st.warning("No clock definitions found in the provided text.")
        else:
            st.divider()

            # ── Summary metrics ─────────────────────────────────────────────
            s = cr_result.stats
            rc1, rc2, rc3, rc4, rc5 = st.columns(5)
            rc1.metric("🕐 Clocks", s["clocks"])
            rc2.metric("🔗 Pairs", s["pairs"])
            rc3.metric("🟢 Correct", s["pairs"] - s["mismatches"] - s["missing"])
            rc4.metric("🔴 Mismatches", s["mismatches"])
            rc5.metric("⬜ Missing", s["missing"])

            # ── Clock Relation Matrix ──────────────────────────────────────
            st.subheader("📊 Clock Relation Matrix")
            n_clocks = len(cr_result.clocks)
            clock_names = [c.name for c in cr_result.clocks]

            # Build pair lookup
            pair_map = {}
            for p in cr_result.pairs:
                key = tuple(sorted([p.clock_a, p.clock_b]))
                pair_map[key] = p

            # Build mismatch lookup
            mismatch_map = {}
            for m in cr_result.mismatches:
                key = tuple(sorted([m.clock_a, m.clock_b]))
                mismatch_map[key] = m

            # Build specified-relation lookup
            spec_map = {}
            for grp in cr_result.existing_groups:
                for (pair_key, grp_type) in grp['pairs']:
                    spec_map[pair_key] = grp_type

            # Render HTML matrix
            html = ['<table style="border-collapse:collapse;font-size:13px">']

            # Header row
            html.append('<tr><td style="padding:6px;font-weight:600"></td>')
            for name in clock_names:
                html.append(f'<td style="padding:6px;font-weight:600;text-align:center;background:#f8f9fa;border:1px solid #dee2e6">{name}</td>')
            html.append('</tr>')

            for i, ca in enumerate(clock_names):
                html.append(f'<tr><td style="padding:6px;font-weight:600;background:#f8f9fa;border:1px solid #dee2e6">{ca}</td>')
                for j, cb in enumerate(clock_names):
                    if i == j:
                        # Diagonal — clock name
                        html.append(f'<td style="padding:6px;text-align:center;border:1px solid #dee2e6;background:#e9ecef;font-weight:600">{ca}</td>')
                    elif i > j:
                        # Lower triangle — skip (mirror of upper)
                        html.append('<td style="padding:4px;border:1px solid #dee2e6"></td>')
                    else:
                        # Upper triangle — relationship
                        key = tuple(sorted([ca, cb]))
                        pair = pair_map.get(key)
                        if pair:
                            mismatch = mismatch_map.get(key)
                            spec_type = spec_map.get(key)

                            # Determine cell color
                            if mismatch:
                                color = "#FEE2E2"  # red — mismatch
                                border = "#EF4444"
                            elif spec_type == pair.inferred_relation:
                                color = "#DCFCE7"  # green — correct
                                border = "#22C55E"
                            elif spec_type:
                                color = "#FEF3C7"  # yellow — maybe OK
                                border = "#F59E0B"
                            elif pair.inferred_relation == "synchronous":
                                color = "#DBEAFE"  # blue — no constraint needed
                                border = "#3B82F6"
                            else:
                                color = "#F3F4F6"  # gray — missing
                                border = "#9CA3AF"

                            rel_abbr = {
                                "asynchronous": "ASYNC",
                                "synchronous": "SYNC",
                                "physically_exclusive": "PHY_EX",
                                "logically_exclusive": "LOG_EX",
                            }.get(pair.inferred_relation, "?")

                            title = f"Inferred: {pair.inferred_relation}\nReason: {pair.reason}"
                            if spec_type:
                                title += f"\nSDC specifies: {spec_type}"
                            if mismatch:
                                title += f"\nMISMATCH: {mismatch.msg[:100]}"

                            html.append(
                                f'<td style="padding:6px;text-align:center;border:2px solid {border};'
                                f'background:{color};cursor:help" title="{title.replace(chr(34), "&quot;")}">'
                                f'{rel_abbr}</td>'
                            )
                html.append('</tr>')
            html.append('</table>')

            st.markdown("".join(html), unsafe_allow_html=True)

            # Legend
            leg1, leg2, leg3, leg4, leg5 = st.columns(5)
            leg1.markdown('<span style="background:#DCFCE7;padding:2px 8px;border-radius:4px;font-size:12px">✅ Correct</span>', unsafe_allow_html=True)
            leg2.markdown('<span style="background:#FEE2E2;padding:2px 8px;border-radius:4px;font-size:12px">🔴 Mismatch</span>', unsafe_allow_html=True)
            leg3.markdown('<span style="background:#DBEAFE;padding:2px 8px;border-radius:4px;font-size:12px">🔵 Sync (no flag)</span>', unsafe_allow_html=True)
            leg4.markdown('<span style="background:#F3F4F6;padding:2px 8px;border-radius:4px;font-size:12px">⬜ Missing</span>', unsafe_allow_html=True)
            leg5.markdown('<span style="background:#FEF3C7;padding:2px 8px;border-radius:4px;font-size:12px">🟡 Needs review</span>', unsafe_allow_html=True)

            st.caption("Hover over cells for details. ASYNC=asynchronous, SYNC=synchronous, PHY_EX=physically exclusive, LOG_EX=logically exclusive.")

            # ── Mismatches ──────────────────────────────────────────────────
            mismatches = [m for m in cr_result.mismatches if m.severity == "warning"]
            if mismatches:
                st.subheader(f"🔴 Mismatches ({len(mismatches)})")
                st.error("These clock relationships are incorrectly specified and may cause SI pessimism or masked timing paths.")
                for m in mismatches:
                    with st.expander(f"🔴 `{m.code}` — {m.clock_a} / {m.clock_b}"):
                        st.markdown(f'<span class="warn-badge">Warning</span>', unsafe_allow_html=True)
                        st.markdown(f"**Specified:** `{m.specified}` → **Expected:** `{m.expected}`")
                        st.markdown(f"**{m.msg}**")

            # ── Missing relationships ──────────────────────────────────────
            missing = [m for m in cr_result.mismatches if m.severity == "info"]
            if missing:
                st.subheader(f"⬜ Missing Constraints ({len(missing)})")
                st.info("These clock pairs have no `set_clock_groups` constraint. Adding one is recommended for clarity.")
                for m in missing:
                    with st.expander(f"⬜ `{m.code}` — {m.clock_a} / {m.clock_b}"):
                        st.markdown(f'<span class="info-badge">Info</span>', unsafe_allow_html=True)
                        st.markdown(f"**Expected:** `{m.expected}`")
                        st.markdown(f"**{m.msg}**")

            # ── All clock pairs table ─────────────────────────────────────
            st.subheader("📋 All Clock Pairs")
            with st.expander(f"View all {len(cr_result.pairs)} pairs"):
                for p in cr_result.pairs:
                    icon = "✅" if p.confidence >= 1.0 else "⚠️"
                    st.markdown(f"{icon} **{p.clock_a}** ↔ **{p.clock_b}**: `{p.inferred_relation}` — {p.reason}")

            # ── Clock definitions ──────────────────────────────────────────
            st.subheader("📄 Clock Definitions")
            with st.expander(f"View {len(cr_result.clocks)} clocks"):
                for c in cr_result.clocks:
                    gen = " (generated)" if c.is_generated else ""
                    master = f" → master: {c.master_clock}" if c.master_clock else ""
                    st.code(f"{c.name}: period={c.period}ns, port={c.source_port}{gen}{master}", language="tcl")

    elif not cr_text:
        st.info("Upload an SDC file or paste text above to analyze clock relationships.")


# ════════════════════════════════════════════════════════════════════════════
# CONSTRAINT COVERAGE TAB
# ════════════════════════════════════════════════════════════════════════════
with tab_coverage:
    st.subheader("📊 Constraint Coverage Analyzer")
    st.caption(
        "Measures which constraint categories are covered vs. missing — "
        "gap analysis for signoff readiness. Identifies what's NOT in your SDC."
    )

    cv_col_up, cv_col_paste = st.columns([1, 2])
    with cv_col_up:
        cv_uploaded = st.file_uploader("Upload .sdc / .tcl / .txt", type=["sdc", "tcl", "txt"], key="cv_upload")
    with cv_col_paste:
        cv_pasted = st.text_area(
            "Or paste SDC text here", height=120,
            placeholder=(
                "set sdc_version 2.2\n"
                "set_units -time ns -capacitance pF\n"
                "create_clock -name clk -period 10.0 [get_ports clk]\n"
                "set_input_delay 2.0 -clock clk [all_inputs]\n"
                "..."
            ),
            key="cv_paste",
        )

    cv_text = None
    if cv_uploaded:
        cv_text = cv_uploaded.read().decode("utf-8", errors="replace")
    elif cv_pasted.strip():
        cv_text = cv_pasted

    if cv_text and st.button("📊 Analyze Coverage", type="primary", use_container_width=True, key="cv_analyze_btn"):
        with st.spinner("Analyzing constraint coverage..."):
            cv_result = parse_sdc_coverage(cv_text)

        if not cv_result.categories:
            st.warning("No constraint categories found.")
        else:
            st.divider()

            # ── Overall score ────────────────────────────────────────────────
            score = cv_result.score
            if score >= 80:
                score_color = "#059669"
                score_label = "Good"
            elif score >= 50:
                score_color = "#d97706"
                score_label = "Needs Work"
            else:
                score_color = "#dc2626"
                score_label = "Incomplete"

            st.markdown(
                f'<div style="text-align:center;margin:12px 0">'
                f'<span style="font-size:56px;font-weight:800;color:{score_color}">{score:.1f}%</span>'
                f'<br><span style="font-size:14px;color:#6b7280">Constraint Coverage — {cv_result.total_present} of {cv_result.total_items} items present</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # ── Summary metrics ─────────────────────────────────────────────
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("📊 Coverage", f"{score:.0f}%")
            mc2.metric("✅ Present", cv_result.total_present)
            mc3.metric("❌ Missing", cv_result.total_missing)
            mc4.metric("📁 Categories", len(cv_result.categories))

            # ── Category cards ──────────────────────────────────────────────
            for cat in cv_result.categories:
                bar_color = "#059669" if cat.score >= 80 else "#d97706" if cat.score >= 50 else "#dc2626"
                with st.expander(f"{cat.icon} {cat.name} — {cat.score:.0f}% ({cat.covered}/{cat.total})", expanded=(cat.score < 80)):
                    # Progress bar
                    st.markdown(
                        f'<div style="background:#e5e7eb;border-radius:6px;height:12px;margin-bottom:12px">'
                        f'<div style="background:{bar_color};height:12px;border-radius:6px;width:{cat.score:.0f}%"></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # Items table
                    for item in cat.items:
                        if item.present:
                            icon = "✅"
                            color = "#059669"
                        elif item.is_critical:
                            icon = "🔴"
                            color = "#dc2626"
                        else:
                            icon = "❌"
                            color = "#6b7280"

                        st.markdown(
                            f'<span style="color:{color};font-weight:600">{icon}</span> '
                            f'<span style="font-size:13px">{item.name}</span>'
                            f' <span style="color:#6b7280;font-size:12px">{item.detail}</span>',
                            unsafe_allow_html=True,
                        )

            # ── Missing items summary ───────────────────────────────────────
            missing_items = []
            for cat in cv_result.categories:
                for item in cat.items:
                    if not item.present:
                        missing_items.append((cat.name, cat.icon, item))

            if missing_items:
                st.subheader(f"⚠️ Missing Items ({len(missing_items)})")
                st.info("These constraints are not defined in your SDC. Critical items (🔴) should be added before signoff.")

                for cat_name, cat_icon, item in missing_items:
                    crit = "🔴" if item.is_critical else "⚪"
                    st.markdown(
                        f"{crit} **{cat_name}** — {item.name}"
                        f"  \n> {item.detail}",
                    )

            # ── Download HTML report ────────────────────────────────────────
            st.divider()
            from reporter import generate_coverage_report
            cov_html = generate_coverage_report(cv_result, "coverage_report")
            st.download_button(
                "📥 Download HTML Report",
                data=cov_html,
                file_name="sdc_coverage_report.html",
                mime="text/html",
                use_container_width=True,
            )

    elif not cv_text:
        st.info("Upload an SDC file or paste text above to analyze constraint coverage.")
