# SDC Tools

A web-based tool for synthesis design constraint files — validate existing SDCs and generate new ones from scratch.

Built with Python + Streamlit. Zero dependencies beyond `streamlit`.

## Features

### Checker / Validator
- **8 error checks** — missing clocks, unconstrained I/Os, invalid case_analysis values, generated clock without -source, virtual clock with set_propagated_clock, and more
- **15 warning checks** — missing hold counterparts, suspicious false paths, CDC without clock groups, incomplete timing derate pairs, half-cycle path issues
- **26 best-practice tips** — missing set_units, no set_max_transition, no timing derate, no group_path, etc.
- Detects **virtual clocks** automatically
- Full **SDC contents summary** (clocks, delays, exceptions, etc.)

### SDC Generator
- **Primary, generated, and virtual clocks** — full switch set for `create_generated_clock` including `-divide_by`, `-multiply_by`, `-duty_cycle`, `-edge_shift`, `-invert`, `-preinvert`, `-combinational`, `-add`
- **I/O constraints** — `-max`/`-min` input and output delays, `set_driving_cell` or `set_input_transition`
- **Design rules** — max fanout, transition, capacitance, min capacitance, max area
- **Operating conditions** and **timing derate** (AOCV)
- **DFT / Scan** — `set_case_analysis` with 0/1/rising/falling, multiple entries, port or pin
- **Disable timing arcs** — per-arc with `-from`/`-to` pins
- **Timing exceptions** — false paths, multicycle paths (hold auto-added), half-cycle paths (`-rise_to`/`-fall_to`)
- **Power constraints** — dynamic and leakage
- **Path groups**, **wire load**, **dont-use cells**
- Native **Download .sdc** button — always works

## Quick Start

```bash
# Clone the repo
git clone https://github.com/RAMA-L7/sdc-tools.git
cd sdc-tools

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

App opens at `http://localhost:8501`

## Deploy to Streamlit Cloud (free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → select your repo → set main file to `app.py`
4. Click **Deploy** — live URL in ~2 minutes

## Project Structure

```
sdc-tools/
├── app.py              ← Streamlit UI (checker + generator tabs)
├── checker.py          ← SDC parser and validation logic
├── generator.py        ← SDC constraint generation logic
├── requirements.txt
└── samples/
    └── example.sdc     ← Sample SDC for testing the checker
```

## Integration with VLSI Hub

This tool is designed to work standalone but also integrates into the [VLSI Hub](https://github.com/YOUR_USERNAME/vlsi-hub) React frontend as the `SDCToolsPage` component.

## License

MIT
