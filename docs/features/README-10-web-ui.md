# Feature 10: Streamlit Web UI

> **Module:** `app.py` · **CLI:** `sdc-tools web` · **Access:** `streamlit run app.py`

---

## Why It's Needed

While the CLI is powerful for automation and CI/CD, interactive constraint development needs a **visual interface**:

- Upload SDCs by drag-and-drop
- See validation results in color-coded expandable cards
- Configure SDC generation with form fields and sliders
- View clock relation matrices as heat-mapped tables
- Download generated SDCs and ZIP archives with one click
- Compare versions side-by-side with colored diffs

The Streamlit web UI wraps all CLI features into a visual dashboard — no terminal knowledge needed.

---

## How It Was Implemented

### Architecture

- **Single-page Streamlit app** (`app.py`) — ~1600 lines of Python
- **7 tabs** — each wrapping a core feature in Streamlit widgets
- **Session state** — persists corners, generated SDCs, analysis results across interactions
- **Inline CSS** — custom badge styles, card coloring, matrix formatting
- **External library** — pandas (corner matrix display), difflib (text diff rendering)

### Tab Structure

| # | Tab | UI Components | Backend Module |
|---|-----|---------------|----------------|
| 1 | 🛡 Checker | File upload, paste, custom rules upload, metrics cards, expandable issues, rule reference | `checker.py`, `custom_rules.py`, `rules_registry.py` |
| 2 | ⚙️ Generator | Form fields (6 sections), live validation, download button, quick MMC, baseline comparison | `generator.py`, `checker.py`, `mmc.py`, `constraint_diff.py` |
| 3 | 🔲 MMC Corner Manager | Preset loader, add/edit form, corner list, import/export JSON, coverage matrix | `corner_manager.py` |
| 4 | 📦 MMC SDC Generator | Template form, corner selection, ZIP download, corner diff view, cross-corner checks | `mmc.py`, `generator.py` |
| 5 | 🔍 Change Analyzer | V1/V2 upload, linked TCL upload, analyze button, metrics, fatal/warning/info expanders, text diff | `constraint_diff.py`, `tcl_resolver.py` |
| 6 | 🕐 Clock Relations | Clock upload, analyze button, metrics, N×N color matrix, mismatch/missing expanders, clock list | `clock_relations.py` |
| 7 | 📊 Coverage | SDC upload, score display, summary metrics, category expanders, missing items summary, HTML report download | `coverage.py`, `reporter.py` |

### Session State Variables

| Variable | Type | Purpose |
|----------|------|---------|
| `st.session_state.corners` | `List[Corner]` | User-defined PVT corners |
| `st.session_state.generated_sdcs` | `Dict[str, str]` | Per-corner SDC text cache |
| `st.session_state.editing_corner_idx` | `int | None` | Which corner is being edited |
| `st.session_state.analyzer_result` | `ChangeAnalysisResult | None` | Diff analysis cache |

---

## Use Cases

| Scenario | Tab | Why |
|----------|-----|-----|
| **Daily constraint editing** | Checker | Quick validation as you edit |
| **New chip kickoff** | Generator | Generate baseline SDC in 2 minutes |
| **Corner definition** | MMC Corner Manager | Configure PVT corners for multi-corner flow |
| **Multi-corner generation** | MMC SDC Generator | Generate all corner SDCs in one click |
| **Pre-ECO review** | Change Analyzer | Check what changed before tapeout |
| **Clock architecture review** | Clock Relations | Verify clock domain isolation |
| **Signoff readiness** | Coverage | Check constraint completeness |

---

## Structural View

```
┌────────────────────────────────────────────────────┐
│  app.py — Streamlit Application                     │
│                                                      │
│  st.set_page_config(layout="wide")                   │
│                                                      │
│  Sidebar:                                            │
│  ├── Version badge (SDC Tools v1.2.0)                │
│  ├── "What's New" changelog                          │
│  └── GitHub link                                     │
│                                                      │
│  7 Tabs:                                             │
│  ┌─────┬─────┬──────┬──────┬──────┬──────┬─────┐    │
│  │ 🛡  │ ⚙️  │ 🔲   │ 📦   │ 🔍  │ 🕐   │ 📊 │    │
│  │Chkr │Gen  │ Mgr  │ MMC  │ Diff │ Clock│Cov  │    │
│  └──┬──┴──┬──┴──┬───┴──┬───┴──┬───┴──┬───┴──┬─┘    │
│     │     │     │      │      │      │      │         │
│     ▼     ▼     ▼      ▼      ▼      ▼      ▼         │
│  checker generator corner mmc.py constraint clock_r coverage│
│  .py    .py    .py   .py    _diff.py relatns  .py   │
│                                              .py     │
│  custom_  SDC-            tcl_      clock_  reporter │
│  rules.py Params   corner_resolver .py    .py       │
│                       _manager.py                    │
│  rules_registry.py     wildcard_                      │
│                        analyzer.py                    │
└──────────────────────────────────────────────────────┘
```

## Flow Diagram

```
User opens browser → http://localhost:8501
                        │
                        ▼
              ┌─────────────────────┐
              │  Sidebar Loading    │
              │  • Version badge    │
              │  • Changelog        │
              │  • GitHub link      │
              └─────────────────────┘
                        │
                        ▼
           ┌───────────────────────────┐
           │  Tab 1: Checker/Validator │
           │                           │
           │  [Upload SDC] [Paste SDC] │
           │  [Custom Rules YAML]      │
           │                           │
           │  ┌─────────────────────┐  │
           │  │ ❌ Errors: 3        │  │
           │  │ ⚠️ Warnings: 8      │  │
           │  │ ℹ️ Info: 12         │  │
           │  │ 🕐 Clocks: 4        │  │
           │  └─────────────────────┘  │
           │                           │
           │  Verdict (error/warn/ok)  │
           │  ┌── Issues (expandable)  │
           │  │ 🔴 SDC-001 — No clock  │
           │  │ 🟡 SDC-024 — No groups │
           │  └────────────────────────│
           │                           │
           │  📋 Rule Reference        │
           │  [Search box] [Filter]    │
           │  [Expandable rules table] │
           └───────────────────────────┘
                        │
           ┌───────────────────────────┐
           │  Tab 2: SDC Generator     │
           │                           │
           │  Left: Form (6 sections)  │
           │  Right: Live SDC preview  │
           │                           │
           │  [Download .sdc]           │
           │                           │
           │  Live Validation results   │
           │  Quick Multi-Corner Gen    │
           │  Compare vs Baseline      │
           └───────────────────────────┘
                        │
           ┌───────────────────────────┐
           │  Tab 3: MMC Corner Manager│
           │                           │
           │  [Load Preset] [Export]   │
           │  [Import JSON]            │
           │                           │
           │  Add/Edit corner form     │
           │  Corner list (expand)     │
           │  Coverage matrix table    │
           └───────────────────────────┘
                        │
           ┌───────────────────────────┐
           │  Tab 4: MMC SDC Generator │
           │                           │
           │  Base template config     │
           │  Corner selection         │
           │  [Generate All]            │
           │  [Download ZIP]            │
           │  Corner diff (A vs B)     │
           │  Cross-corner checks      │
           │  Per-corner SDC previews  │
           └───────────────────────────┘
                        │
           ┌───────────────────────────┐
           │  Tab 5: Change Analyzer   │
           │                           │
           │  [Upload V1] [Paste V1]   │
           │  [Upload V2] [Paste V2]   │
           │  [V1 linked TCL]          │
           │  [V2 linked TCL]          │
           │  [Analyze Changes]         │
           │                           │
           │  Metrics: Fatal/Warn/Info │
           │  Fatal changes (expand)   │
           │  Warnings (expand)        │
           │  Info changes (expand)    │
           │  Text diff (colored)      │
           └───────────────────────────┘
                        │
           ┌───────────────────────────┐
           │  Tab 6: Clock Relations   │
           │                           │
           │  [Upload] [Paste SDC]      │
           │  [Analyze]                 │
           │                           │
           │  Metrics: Clocks/Pairs/   │
           │           Mismatches       │
           │  N×N Color Relation Matrix│
           │  Mismatch expanders       │
           │  Missing constraints      │
           │  All pairs list           │
           │  Clock definitions        │
           └───────────────────────────┘
                        │
           ┌───────────────────────────┐
           │  Tab 7: Coverage          │
           │                           │
           │  [Upload] [Paste SDC]      │
           │  [Analyze Coverage]        │
           │                           │
           │  Large score: 56.4%       │
           │  Metrics: 22/39 items     │
           │  Category expanders       │
           │  (each with progress bar) │
           │  Missing items summary    │
           │  [Download HTML Report]   │
           └───────────────────────────┘
```

## CLI Usage

```bash
# Launch the web UI
sdc-tools web

# Or directly with Streamlit
streamlit run app.py

# Docker
docker run -p 8501:8501 ramal7/sdc-tools web
```

## Python API (Not applicable — UI-only module)

The web UI is a presentation layer. All backend logic lives in the individual modules:
- `checker.py` — validation
- `generator.py` — SDC generation
- `corner_manager.py` — corner management
- `mmc.py` — multi-corner operations
- `constraint_diff.py` — semantic diff
- `clock_relations.py` — clock analysis
- `coverage.py` — coverage analysis
- `custom_rules.py` — custom rules
- `rules_registry.py` — rule lookup
- `reporter.py` — HTML reports

## UI Badge Styles

Custom CSS badges used across all tabs:

| Badge | Class | Background | When Used |
|-------|-------|------------|-----------|
| 🔴 Error | `err-badge` | #FCEBEB | Error items |
| 🟡 Warning | `warn-badge` | #FAEEDA | Warning items |
| 🔵 Info | `info-badge` | #E6F1FB | Info items |
| 💀 Fatal | `fatal-badge` | #FDE2E2 | Fatal changes |
| ✅ Passed | `note-badge` | #EAF3DE | Custom rules pass |

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*