# SDC Tools

> **Open-source SDC constraint development, validation, and verification toolkit for VLSI synthesis engineers.**

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.2.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-yellow" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-gray" alt="Platform">
  <img src="https://img.shields.io/badge/PyPI-sdc--tools-purple" alt="PyPI">
  <img src="https://img.shields.io/badge/Docker-ramal7%2Fsdc--tools-orange" alt="Docker">
</p>

---

## What is SDC Tools?

**SDC (Synopsys Design Constraints)** files are the standard way to define timing, power, and design rule constraints for digital synthesis. A single mistake in an SDC file — a missing clock, an incorrect derate, an overly broad wildcard — can cause silicon failure or thousands of false timing violations.

SDC Tools is a **complete toolkit** for the entire SDC lifecycle:

```
  Write ──▶ Validate ──▶ Generate ──▶ Review ──▶ Signoff
   │            │             │            │            │
   │            │             │            │            │
   ▼            ▼             ▼            ▼            ▼
  Rules      Checker      Generator    Diff/Matrix   Reports
  Engine                                          + Coverage
```

---

## 🚀 Quick Start

### Install from PyPI (recommended)
```bash
pip install sdc-tools
sdc-tools check sample.sdc          # validate
sdc-tools generate --design MY_CHIP --clock clk=10.0  # generate
sdc-tools --help                     # see all commands
```

### Install from source
```bash
git clone https://github.com/RAMA-L7/sdc-tools.git
cd sdc-tools
pip install -e ".[web]"
sdc-tools web                        # launch browser UI
```

### Docker
```bash
docker build -t sdc-tools .
docker run -it sdc-tools check sample.sdc         # CLI
docker run -p 8501:8501 ramal7/sdc-tools web      # Web UI
```

---

## 📋 Feature Overview (10 Major Features)

| # | Feature | Module | CLI Command | Description |
|---|---------|--------|-------------|-------------|
| 1 | [**SDC Checker / Validator**](docs/features/README-01-checker.md) | `checker.py` | `sdc-tools check` | 40+ semantic checks: errors, warnings, best practices |
| 2 | [**SDC Generator**](docs/features/README-02-generator.md) | `generator.py` | `sdc-tools generate` | Generate complete SDC from parameters in seconds |
| 3 | [**Constraint Change Analyzer**](docs/features/README-03-diff.md) | `constraint_diff.py` | `sdc-tools diff` | Semantic diff with TCL variable resolution + wildcard drift |
| 4 | [**Clock Relation Analyzer**](docs/features/README-04-clock-relations.md) | `clock_relations.py` | `sdc-tools analyze clock-relations` | Infer correct clock relationships and detect mismatches |
| 5 | [**Multi-Corner Manager (MMC)**](docs/features/README-05-mmc.md) | `corner_manager.py` + `mmc.py` | `sdc-tools corners` | PVT corner presets, per-corner SDC generation, ZIP packaging |
| 6 | [**Constraint Coverage Gap Analysis**](docs/features/README-06-coverage.md) | `coverage.py` | `sdc-tools coverage` | 39-item gap analysis across 6 constraint categories |
| 7 | [**Custom Rules Engine**](docs/features/README-07-custom-rules.md) | `custom_rules.py` | `sdc-tools check --custom-rules` | YAML-based project-specific validation policies |
| 8 | [**Rules Registry**](docs/features/README-08-rules-registry.md) | `rules_registry.py` | `sdc-tools rules` | Centralized documentation of all 60+ rule codes |
| 9 | [**HTML Signoff Reports**](docs/features/README-09-reports.md) | `reporter.py` | `sdc-tools report` | Self-contained, zero-dependency HTML reports |
| 10 | [**Streamlit Web UI**](docs/features/README-10-web-ui.md) | `app.py` | `sdc-tools web` | Interactive browser UI with 7 visual tabs |

---

## 🔍 Check Your SDC

```bash
sdc-tools check design.sdc
# Output:
#   Errors:   3    (SDC-001, SDC-005, SDC-006)
#   Warnings: 8    (SDC-024, SDC-030, ...)
#   Info:    12    (best practice suggestions)
#
#   [SDC-001] No create_clock defined — all paths unconstrained.
#   [SDC-024] 4 clocks but no set_clock_groups — CDC un-flagged.
```

With JSON output for CI integration:
```bash
sdc-tools check design.sdc --json
sdc-tools check design.sdc --junit --output results.xml
```

With custom rules:
```bash
sdc-tools check design.sdc --custom-rules my_policy.yaml --custom-rules team_rules.yaml
```

## ⚙️ Generate SDC

```bash
sdc-tools generate \
  --design MY_CHIP \
  --clock clk_core=5.0:sys_clk \
  --clock clk_slow=20.0:slow_clk \
  --uncertainty 0.15 \
  --operating-condition WORST \
  --derate \
  --propagated \
  --output my_chip.sdc
```

## 🔍 Compare SDC Versions

```bash
sdc-tools diff old.sdc new.sdc \
  --linked-v1 params_v1.tcl \
  --linked-v2 params_v2.tcl \
  --verbose
# Output:
#   FATAL  [CHG-FP-001]  False path removed — timing now checked on this path
#   WARN   [CHG-CK-001]  Clock period decreased from 5ns to 4ns
#   INFO   [CHG-GEN-001] New constraint added
```

## 🕐 Clock Relation Analysis

```bash
sdc-tools analyze clock-relations design.sdc
# Output:
#   Clocks: 4    Pairs: 6    Mismatches: 2
#   [SDC-060] WARNING  CLKA vs CLKB
#     Specified: -asynchronous
#     Expected:  -physically_exclusive
```

## 🔲 Multi-Corner SDC Generation

```bash
sdc-tools corners list                            # see presets
sdc-tools corners show "Classic 3-corner"        # view details
```

```bash
# Generate per-corner SDCs via the Web UI
sdc-tools web
# → MMC Corner Manager tab → load preset → generate
```

## 📊 Constraint Coverage

```bash
sdc-tools coverage design.sdc
# Output:
#   Overall Coverage: 56.4% (22/39 items)
#
#   🕐 Clocks: 78%       [#####.....] (7/9)
#   🔌 I/O: 67%          [####......] (4/6)
#   ⚠️ Exceptions: 71%   [#####.....] (5/7)
#   📏 Design Rules: 83% [######....] (5/6)
#   📊 AOCV/Derate: 0%   [..........] (0/5) ← critical gap
#   ⚡ Power/DFT: 33%    [###.......] (2/6)

sdc-tools coverage design.sdc --missing-only    # compact view
sdc-tools coverage design.sdc --json            # for automation
```

## 📋 Rules Lookup

```bash
sdc-tools rules list                             # all 60+ rules
sdc-tools rules list --severity error             # errors only
sdc-tools rules list --search derate              # search by keyword
sdc-tools rules show SDC-060                      # single rule details
```

## 📋 Custom Rules YAML

```yaml
# my_policy.yaml
name: My Team Policies
version: "1.0"
rules:
  - id: MY-001
    name: "Clock period ≤ 10ns"
    severity: warning
    command: create_clock
    condition: value_above
    field: period
    threshold: 10.0
    message: "Clock period {value}ns exceeds 10ns limit"

  - id: MY-002
    name: "Propagated clock required"
    severity: error
    command: set_propagated_clock
    condition: present
    message: "No set_propagated_clock — required by policy"
```

## 📋 HTML Signoff Reports

```bash
sdc-tools report check design.sdc -o quality_report.html
sdc-tools report diff old.sdc new.sdc -o diff_report.html
sdc-tools report clock-relations design.sdc -o clock_report.html
sdc-tools report coverage design.sdc -o coverage_report.html
```

---

## 📦 Project Structure

```
sdc-tools-main/
│
├── core modules ──────────────────────────────
│   ├── checker.py           # SDC validation (40+ checks)
│   ├── generator.py         # SDC generation from params
│   ├── constraint_diff.py   # Semantic SDC diff + change rules
│   ├── clock_relations.py   # Clock relation inference + mismatches
│   ├── corner_manager.py    # PVT corner data model + presets
│   ├── mmc.py               # Multi-corner SDC operations
│   ├── coverage.py          # Constraint coverage gap analysis
│   ├── custom_rules.py      # YAML-based custom validation rules
│   ├── rules_registry.py    # Central rule code documentation (60+)
│   ├── reporter.py          # HTML signoff report generator
│   ├── tcl_resolver.py      # TCL $variable resolution
│   └── wildcard_analyzer.py # Wildcard pattern risk analysis
│
├── interfaces ─────────────────────────────────
│   ├── cli.py               # Command-line interface (9 commands)
│   └── app.py               # Streamlit web UI (7 tabs)
│
├── packaging & deployment ─────────────────────
│   ├── pyproject.toml       # PyPI package configuration
│   ├── Dockerfile           # Container image (Python 3.11-slim)
│   ├── .dockerignore        # Docker build exclusions
│   └── __init__.py          # Package init
│
├── sample files ───────────────────────────────
│   ├── samples/
│   │   ├── example.sdc                 # Full example SDC file
│   │   ├── constraint_diff_v1.sdc      # Diff demo: version 1
│   │   ├── constraint_diff_v2.sdc      # Diff demo: version 2
│   │   └── clock_relations.sdc         # Clock relations demo
│   └── custom_rules_example.yaml       # 10 example custom rules
│
├── git hooks & CI ─────────────────────────────
│   ├── .pre-commit-config.yaml         # Pre-commit framework config
│   ├── .pre-commit-hooks/sdc-check.sh  # Standalone git hook
│   └── sdc-tools.cmd                   # Windows CLI wrapper
│
├── documentation ──────────────────────────────
│   ├── README.md                       # This file
│   └── docs/features/                  # Detailed feature docs
│       ├── README-01-checker.md         # SDC Checker / Validator
│       ├── README-02-generator.md       # SDC Generator
│       ├── README-03-diff.md            # Constraint Change Analyzer
│       ├── README-04-clock-relations.md # Clock Relation Analyzer
│       ├── README-05-mmc.md             # Multi-Corner Manager
│       ├── README-06-coverage.md        # Constraint Coverage Gap
│       ├── README-07-custom-rules.md    # Custom Rules Engine
│       ├── README-08-rules-registry.md  # Rules Registry
│       ├── README-09-reports.md         # HTML Signoff Reports
│       └── README-10-web-ui.md          # Streamlit Web UI
│
├── MIT License                          # Open-source (MIT)
└── .gitignore                           # Git exclusions
```

---

## 🖥️ CLI Reference

| Command | Purpose | Key Flags |
|---------|---------|-----------|
| `check` | Validate SDC | `--json`, `--junit`, `--custom-rules`, `--verbose` |
| `generate` | Generate SDC | `--clock`, `--design`, `--derate`, `--operating-condition` |
| `diff` | Semantic diff | `--linked-v1`, `--linked-v2`, `--json`, `--verbose` |
| `corners` | Manage corners | `list`, `show <name>` |
| `analyze` | Deep analysis | `clock-relations`, `--json` |
| `rules` | Rule lookup | `list`, `show <code>`, `--module`, `--severity`, `--search` |
| `coverage` | Gap analysis | `--json`, `--missing-only` |
| `report` | HTML reports | `check`, `diff`, `clock-relations`, `coverage` |
| `web` | Launch browser UI | (opens `http://localhost:8501`) |

---

## 🏗️ Design Principles

1. **Zero external dependencies** for core validation (stdlib only)
2. **Single Python files** — no complex package hierarchies
3. **Fail-fast on errors** — CLI exits with code 1 if any errors found
4. **Graceful optional features** — YAML (PyYAML optional), Web (Streamlit optional)
5. **CI-friendly** — JUnit XML, JSON output, exit codes, pre-commit hooks
6. **Self-contained reports** — HTML with inline CSS, no CDN, no JS

---

## 📚 Documentation

**Detailed feature documentation** — each feature has its own README with:
- Why it's needed (problem statement)
- How it was implemented (technical architecture)
- Use cases (when/why to use it)
- Structural view (ASCII diagrams)
- Flow diagrams (step-by-step)
- CLI usage examples
- Python API examples
- Configuration reference

→ **[Feature Documentation Index](docs/features/)**

---

## 🧪 Test Samples

```bash
# Run all available samples through the checker
sdc-tools check samples/example.sdc --verbose
sdc-tools coverage samples/example.sdc
sdc-tools analyze clock-relations samples/clock_relations.sdc
sdc-tools diff samples/constraint_diff_v1.sdc samples/constraint_diff_v2.sdc
```

---

## 🤝 Contributing

Contributions welcome! The project is organized for easy extension:

- **Add a new checker rule:** Edit `checker.py` (add condition) + `rules_registry.py` (add documentation)
- **Add a new custom condition:** Edit `custom_rules.py` (add `@_cond("name")` handler)
- **Add a new coverage item:** Edit `coverage.py` (add to appropriate category)
- **Add a new report section:** Edit `reporter.py` (add generator function)
- **Add a new Streamlit tab:** Edit `app.py` (add to `st.tabs()` list)

---

## 📜 License

**MIT License** — free for commercial and non-commercial use.

---

## 🙏 Acknowledgments

Built with deep respect for:
- [Ausdia](https://www.ausdia.com/) — TimeVision constraint analysis tool and their excellent blog posts on SDC pitfalls
- [Synopsys](https://www.synopsys.com/glossary/what-is-sdc.html) — SDC standard and tool documentation
- [OpenCores](https://opencores.org/) — open-source digital design community

---

*SDC Tools is an open-source project by RAMA-L7 — an MIT-licensed open-core VLSI constraint toolkit.*
