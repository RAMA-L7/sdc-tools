# Feature 4: Clock Relation Analyzer

> **Module:** `clock_relations.py` · **CLI:** `sdc-tools analyze clock-relations` · **UI:** Clock Relations Tab · **Codes:** SDC-060..063

---

## Why It's Needed

Incorrect `set_clock_groups` constraints are one of the most common and dangerous SDC mistakes:

- **Marking physically exclusive clocks as asynchronous** causes unnecessary Crosstalk/SI analysis on paths that can never physically exist
- **Marking synchronous clocks as exclusive** masks real setup/hold timing paths, leaving them unoptimized — can cause silicon failure
- **Missing clock group constraints** cause all cross-clock paths to be analyzed as synchronous, over-constraining the design

The Clock Relation Analyzer infers the _correct_ relationship for every clock pair by analyzing clock definitions (source ports, periods, parent-child relationships) and comparing against what the SDC actually specifies. It's inspired by [Ausdia's Seemingly Simple Clock Relations Quiz](https://www.ausdia.com/blog/5/seemingly-simple-clock-relations-quiz/filter/0).

---

## How It Was Implemented

### Clock Inference Engine

5 rules determine the correct relationship between any two clocks:

| Rule | Condition | Inferred Relationship |
|------|-----------|----------------------|
| **Rule 1** | Parent-child (generated from master) | synchronous |
| **Rule 2** | Both generated from the same master | synchronous (siblings) |
| **Rule 3** | Same source port, different periods | physically_exclusive |
| **Rule 4** | Same source port, same period | physically_exclusive (duplicates) |
| **Rule 5** | Different source ports, no common master | asynchronous |

### Output

- **`RelationAnalysisResult`** — contains all parsed clocks, inferred pairs, existing groups, and mismatches
- **Stats** — clocks, pairs, synchronous, asynchronous, physically_exclusive, mismatches, missing
- **Mismatch codes:**
  - `SDC-060` — Marked as asynchronous, should be physically_exclusive (warning)
  - `SDC-061` — Marked exclusive, but clocks are synchronous (warning)
  - `SDC-062` — No constraint for async/exclusive pair (info)
  - `SDC-063` — Wrong exclusion type (info)

---

## Use Cases

| Scenario | Why |
|----------|-----|
| **CDC verification** | Ensure all asynchronous clock pairs are properly flagged |
| **SI analysis setup** | Avoid unnecessary Crosstalk analysis on exclusive clocks |
| **Pre-synthesis check** | Catch incorrect clock groups before they mask timing paths |
| **Multi-clock design review** | Understand relationships between all clock domains |

---

## Structural View

```
SDC Text
    │
    ▼
┌──────────────────────────────┐
│ parse_clocks_from_sdc(text)  │
│                              │
│  create_clock: name, period, │
│    source_port, is_virtual   │
│                              │
│  create_generated_clock:     │
│    name, period, master,     │
│    divide_by                 │
│                              │
│  Returns List[ClockDefCK]    │
└──────────────────────────────┘
    │
    ▼
┌──────────────────────────────┐
│ For all C(N,2) clock pairs: │
│ infer_relation(ca, cb)       │
│                              │
│  Rule 1-5 (see above)        │
│                              │
│  Returns ClockPair:          │
│  {inferred_relation, reason} │
└──────────────────────────────┘
    │
    ▼
┌──────────────────────────────┐
│ _parse_existing_groups(text) │
│                              │
│  set_clock_groups:           │
│  -asynchronous               │
│  -logically_exclusive        │
│  -physically_exclusive       │
│                              │
│  Returns [{type, groups,     │
│    pairs, raw}]              │
└──────────────────────────────┘
    │
    ▼
┌──────────────────────────────┐
│ _find_mismatches(pairs,      │
│   existing_groups)           │
│                              │
│  Compare inferred vs actual  │
│  → List[ClockMismatch]       │
│                              │
│  SDC-060: async→phy_excl     │
│  SDC-061: excl→sync          │
│  SDC-062: missing constraint │
│  SDC-063: wrong type         │
└──────────────────────────────┘
```

## Flow Diagram

```
Input: SDC text with clocks and set_clock_groups
                │
                ▼
     ┌──────────────────────┐
     │ Parse all clocks     │
     │ (primary + generated)│
     └──────────┬───────────┘
                │
                ▼
     ┌──────────────────────┐
     │ For each clock pair  │
     │ (i, j) where i < j:  │
     └──────────┬───────────┘
                │
         ┌──────┴──────┐
         ▼              ▼
   Same source?    Different source?
   ────────────    ────────────────
   │                           │
   ▼                           ▼
Same period?             Common master?
  Yes → PHY_EXCL           Yes → SYNC
  No  → PHY_EXCL           No  → ASYNC
               │
               ▼
     ┌──────────────────────┐
     │ Parse                │
     │ set_clock_groups     │
     └──────────┬───────────┘
                │
                ▼
     ┌──────────────────────┐
     │ Compare inferred vs  │
     │ specified            │
     └──────────┬───────────┘
                │
       ┌────────┴────────┐
       ▼                  ▼
   Match?            Mismatch?
   ───────            ─────────
   No action          SDC-060/061
                       SDC-062/063
                │
                ▼
       ┌──────────────────┐
       │ RelationAnalysis │
       │ Result           │
       │ • clocks[]       │
       │ • pairs[]        │
       │ • mismatches[]   │
       │ • stats{}        │
       └──────────────────┘
```

---

## CLI Usage

```bash
# Basic analysis
sdc-tools analyze clock-relations design.sdc

# JSON output
sdc-tools analyze clock-relations design.sdc --json

# Verbose — show all clock pairs and definitions
sdc-tools analyze clock-relations design.sdc --verbose

# Save to file
sdc-tools analyze clock-relations design.sdc --output analysis.txt
```

## Python API

```python
import clock_relations

with open("design.sdc") as f:
    text = f.read()

result = clock_relations.analyze_clock_relations(text)

print(f"{result.stats['clocks']} clocks, {result.stats['pairs']} pairs")
print(f"{result.stats['mismatches']} mismatches")

for m in result.mismatches:
    print(f"  [{m.code}] {m.clock_a} vs {m.clock_b}")
    print(f"    Specified: {m.specified}")
    print(f"    Expected:  {m.expected}")
    print(f"    {m.msg}")

# Access parsed clock definitions
for c in result.clocks:
    print(f"{c.name}: period={c.period}ns, port={c.source_port}")

# Access all inferred pairs
for p in result.pairs:
    print(f"{p.clock_a} ↔ {p.clock_b}: {p.inferred_relation}")
```

## UI: Clock Relation Matrix

The Streamlit UI renders a color-coded N×N matrix:

```
        CLKA   CLKB   CLKC
CLKA    SYNC   PHY_EX ASYNC
CLKB    ─      SYNC   ASYNC
CLKC    ─      ─      SYNC

Legend:
  ✅ Green  = Correct (specified matches inferred)
  🔴 Red    = Mismatch (incorrect constraint)
  🔵 Blue   = Synchronous (no constraint needed)
  ⬜ Gray   = Missing constraint
  🟡 Yellow = Needs review
```

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*