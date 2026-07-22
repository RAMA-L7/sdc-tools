# ============================================================
# clock_relations.sdc — Blog post quiz example
# Source: Ausdia "Seemingly Simple Clock Relations Quiz"
# https://www.ausdia.com/blog/5/seemingly-simple-clock-relations-quiz/filter/0
#
# CLKA and CLKB share port CLKAB (physically exclusive)
# CLKC is on a separate port (asynchronous to CLKA/CLKB)
# CLKA_DIV2 and CLKB_DIV2 are generated from CLKA and CLKB
#
# The set_clock_groups below contain INCORRECT constraints
# for the analyzer to detect.
# ============================================================

set sdc_version 2.2
set_units -time ns -capacitance pF

# ── Clock definitions ─────────────────────────────────────────
create_clock -name CLKA  -period 1.00 [get_ports CLKAB]
create_clock -name CLKB  -period 1.50 [get_ports CLKAB] -add
create_clock -name CLKC  -period 2.30 [get_ports CLKC]

create_generated_clock -name CLKA_DIV2 -divide_by 2 \
  -source [get_ports CLKAB] -master_clock CLKA \
  [get_pins U_DIV2A/Q]

create_generated_clock -name CLKB_DIV2 -divide_by 2 \
  -source [get_ports CLKAB] -master_clock CLKB \
  [get_pins U_DIV2B/Q]

# ── Clock group constraints (QUIZ — some are INCORRECT) ───────

# INCORRECT: CLKA/CLKB share port CLKAB → should be -physically_exclusive
# Using -asynchronous causes unnecessary Crosstalk/SI analysis
set_clock_groups -asynchronous \
  -group [get_clocks CLKA] \
  -group [get_clocks CLKB]

# INCORRECT: CLKB/CLKB_DIV2 are parent-child (synchronous)
# Marking as -logically_exclusive masks real timing paths
set_clock_groups -logically_exclusive \
  -group [get_clocks CLKB] \
  -group [get_clocks CLKB_DIV2]

# CORRECT: CLKB and CLKC are on different ports → asynchronous
set_clock_groups -asynchronous \
  -group [get_clocks CLKB] \
  -group [get_clocks CLKC]

# CORRECT: CLKA and CLKC are on different ports → asynchronous
set_clock_groups -asynchronous \
  -group [get_clocks CLKC] \
  -group [get_clocks CLKA]
