# Feature 5: Multi-Corner Manager (MMC)

> **Modules:** `corner_manager.py`, `mmc.py` · **CLI:** `sdc-tools corners`, `sdc-tools report check` · **UI:** MMC Corner Manager Tab, MMC SDC Generator Tab

---

## Why It's Needed

Modern digital designs must work across multiple PVT (Process-Voltage-Temperature) corners — worst-case (slow/slow, low voltage, high temp), typical, and best-case (fast/fast, high voltage, low temp). Each corner requires different timing derate values, clock uncertainties, and operating conditions.

The MMC system provides:
1. **Predefined corner presets** — 3-corner, 5-corner, 8-corner collections ready to use
2. **Per-corner SDC generation** — generate a complete SDC for each corner from a base template
3. **Cross-corner consistency checks** — detect missing clocks, differing exceptions across corners
4. **Corner diff** — compare SDCs between corners to see what changed
5. **ZIP packaging** — bundle all corners into a single download

Inspired by [Ausdia's analysis of MMMC complexity](https://www.ausdia.com/blog/7/taming-mmmc-mayhem/filter/0).

---

## How It Was Implemented

### Corner Manager (`corner_manager.py`)

- **`Corner` dataclass** — name, operating_condition, voltage, temperature, process_type, 4 derate values, uncertainty_scale
- **4 presets** — Classic 3-corner, Industrial 5-corner, Full 8-corner signoff, Custom (empty)
- **Validation** — range checks on voltage (0.3–1.5V), temperature (-55–175°C), derate values (0.5–1.5)
- **Serialization** — JSON import/export for sharing corner definitions
- **Corner matrix** — summary table of all corners with attributes

### MMC Operations (`mmc.py`)

3 main functions:

1. **`generate_corner_sdcs(template, corners)`** — clone base SDCParams for each corner, apply corner-specific overrides (operating_conditions, derate, uncertainty_scale), generate individual SDCs
2. **`check_sdc_multi(sdc_dict)`** — run checker on each corner individually, then cross-corner consistency checks (SDC-050: clock mismatch, SDC-051: period diff, SDC-053: missing exceptions)
3. **`diff_corners(sdc_a, sdc_b, name_a, name_b)`** — normalise both SDCs (strip comments/headers), run SequenceMatcher, classify each line as equal/added/removed/changed, infer section names
4. **`create_corner_zip(sdc_dict)`** — package all corner SDCs into a ZIP archive (in-memory BytesIO)

### Cross-Corner Checks

| Code | Check | Severity |
|------|-------|----------|
| SDC-050 | Clock names differ between corners | warning |
| SDC-051 | Clock periods differ (may be intentional) | info |
| SDC-053 | Timing exceptions missing in some corners | warning |
| SDC-054 | Derate values not monotonically ordered | warning |

---

## Use Cases

| Scenario | Why |
|----------|-----|
| **Signoff preparation** | Generate all corner SDCs in one click |
| **Multi-corner flow setup** | Quickly configure 3/5/8 corner flows |
| **Cross-corner debugging** | Diff corners to understand unexpected timing differences |
| **Team collaboration** | Export/import corner JSON definitions between projects |
| **Synthesis handoff** | ZIP all corner SDCs for the implementation team |

---

## Structural View

```
┌────────────────────┐      ┌──────────────────────┐
│  CORNER_PRESETS    │      │  Corner dataclass    │
│                    │      │  • name              │
│  Classic 3-corner  │      │  • operating_cond    │
│  Industrial 5      │      │  • voltage           │
│  Full 8-corner     │      │  • temperature       │
│  Custom (empty)    │      │  • process_type      │
│                    │      │  • derate cell E/L   │
│  corner_manager.py │      │  • derate net E/L    │
└────────────────────┘      │  • uncertainty_scale │
         │                  └──────────────────────┘
         ▼                            │
┌────────────────────┐               │
│  mmc.py            │               │
│                    │               │
│  generate_         │◀──────────────┘
│  corner_sdcs()     │  template + corners
│                    │
│  ┌─ Clone SDCParams for each corner
│  │  - Scale uncertainty
│  │  - Set operating_conditions
│  │  - Set derate values
│  │  - Suffix design name
│  └─ generate_sdc() for each
│
│  check_sdc_multi() │─── Individual + cross-corner
│  diff_corners()    │─── Normalized semantic diff
│  create_corner_zip()│─── ZIP packaging
└────────────────────┘
```

## Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  CLI: sdc-tools corners list/show                        │
│  UI:  MMC Corner Manager Tab                             │
│                                                          │
│  1. Load preset or create corners manually               │
│  2. Validate each corner (range checks)                  │
│  3. Export/import JSON                                   │
│  4. Corner coverage matrix                               │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  UI: MMC SDC Generator Tab / Quick MMC (Gen tab)        │
│                                                          │
│  1. Configure base SDC template                          │
│     (clocks, I/O, design rules, etc.)                    │
│                                                          │
│  2. Select which corners to generate                     │
│                                                          │
│  3. mmc.generate_corner_sdcs()                           │
│     ┌────────────────────────────────────────┐           │
│     │ For corner in selected_corners:        │           │
│     │   clone SDCParams                      │           │
│     │   override: oper_cond, derate, unc     │           │
│     │   generate_sdc(cloned)                 │           │
│     │   prepend corner header                │           │
│     │   sdc_dict[corner.name] = sdc_text     │           │
│     └────────────────────────────────────────┘           │
│                                                          │
│  4. Results                                              │
│     ├─ Download All (.zip)                               │
│     ├─ Download individual corner SDCs                   │
│     ├─ Cross-corner consistency checks                  │
│     ├─ Corner diff (A vs B)                             │
│     └─ Per-corner SDC previews                          │
└──────────────────────────────────────────────────────────┘
```

---

## CLI Usage

```bash
# List available presets
sdc-tools corners list

# Show preset details
sdc-tools corners show "Classic 3-corner"
sdc-tools corners show "Industrial 5-corner"

# Partial name match
sdc-tools corners show "Industrial"
```

## Python API

```python
from corner_manager import Corner, CORNER_PRESETS, validate_corner
from mmc import generate_corner_sdcs, check_sdc_multi, diff_corners, create_corner_zip
from generator import SDCParams, ClockDef

# Load corners from preset
corners = CORNER_PRESETS["Classic 3-corner (Worst/Typ/Best)"]

# Or create custom corner
corners = [
    Corner(
        name="SSG_0P72V_M40C",
        operating_condition="SSG_0P72V_M40C",
        voltage=0.72, temperature=-40.0, process_type="SSG",
        derate_cell_early=1.08, derate_cell_late=0.92,
    ),
]

# Validate
for c in corners:
    errors = validate_corner(c)
    assert errors == [], f"Corner {c.name}: {errors}"

# Generate per-corner SDCs
template = SDCParams(design_name="MY_CHIP", clocks=[ClockDef(...)])
sdc_dict = generate_corner_sdcs(template, corners)
# Returns {"SSG_0P72V_M40C": "sdc text...", ...}

# Cross-corner consistency
result = check_sdc_multi(sdc_dict)
print(f"{len(result.errors)} errors, {len(result.warnings)} warnings")

# Diff two corners
diff = diff_corners(sdc_dict["WORST"], sdc_dict["BEST"], "WORST", "BEST")

# ZIP packaging
zip_bytes = create_corner_zip(sdc_dict)
with open("corners.zip", "wb") as f:
    f.write(zip_bytes)
```

## Preset Details

| Preset | Corners | Use Case |
|--------|---------|----------|
| **Classic 3-corner** | WORST (SSG), TYPICAL (TT), BEST (FFG) | Standard signoff |
| **Industrial 5-corner** | 3 + SSG low-V, FFG high-V | Extended voltage range |
| **Full 8-corner** | 5 + SS/FF/TT extra | Comprehensive signoff |

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*