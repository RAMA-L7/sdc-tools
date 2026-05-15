"""
SDC Tools — Streamlit App
Checker + Generator for synthesis design constraint files.
"""

import streamlit as st
from checker import check_sdc
from generator import (
    SDCParams, ClockDef, FalsePath, MultiCyclePath,
    HalfCyclePath, CaseAnalysisEntry, DisableArc,
    PathGroup, generate_sdc
)

st.set_page_config(
    page_title="SDC Tools",
    page_icon="🔧",
    layout="wide",
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: 600; }
.err-badge  { background:#FCEBEB; color:#A32D2D; border:1px solid #F09595; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.warn-badge { background:#FAEEDA; color:#633806; border:1px solid #FAC775; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.info-badge { background:#E6F1FB; color:#0C447C; border:1px solid #85B7EB; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
.note-badge { background:#EAF3DE; color:#27500A; border:1px solid #97C459; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:600; }
code { font-family: monospace; background:#f3f4f6; padding:1px 6px; border-radius:4px; font-size:12px; }
</style>
""", unsafe_allow_html=True)

st.title("🔧 SDC Tools")
st.caption("Validate existing constraints · Generate a complete SDC for your design")

tab_checker, tab_generator = st.tabs(["🛡 Checker / Validator", "⚙️ SDC Generator"])


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
