# ============================================================
# constraint_diff_v1.sdc — Original constraints (V1)
# This file is IDENTICAL to V2 — the differences are in the
# linked TCL variable files (variables_v1.tcl vs variables_v2.tcl)
# ============================================================
set sdc_version 2.2
set_units -time ns -capacitance pF

# Include variable definitions
source variables.tcl

# ── Clocks ───────────────────────────────────────────────────
create_clock -name clk_core -period 5.0 [get_ports clk]
create_clock -name clk_io   -period 10.0 [get_ports clk_io]

set_clock_uncertainty -setup 0.15 [get_clocks clk_core]
set_clock_uncertainty -hold  0.075 [get_clocks clk_core]

# CDC
set_clock_groups -asynchronous \
  -group [get_clocks clk_core] \
  -group [get_clocks clk_io]

# ── Static paths (uses variable $STATIC_PINS) ────────────────
# V1: $STATIC_PINS = [get_pins *static_inst*]  (broad)
# V2: $STATIC_PINS = [get_pins *static_inst1*] (narrower)
set_false_path -through $STATIC_PINS

# ── Power control logic (uses variable $PWR_PINS) ────────────
# V1: $CYCLE = 4
# V2: $CYCLE = 2
set_multicycle_path -setup $CYCLE -through $PWR_PINS -to [get_pins U_RCV_REG/D]
set_multicycle_path -hold [expr {$CYCLE - 1}] -through $PWR_PINS -to [get_pins U_RCV_REG/D]

# ── I/O constraints ──────────────────────────────────────────
set_input_delay -max 1.2 -clock clk_core [remove_from_collection [all_inputs] [get_ports {clk clk_io rst_n}]]
set_input_delay -min 0.4 -clock clk_core [remove_from_collection [all_inputs] [get_ports {clk clk_io rst_n}]]

set_output_delay -max 1.5 -clock clk_core [all_outputs]
set_output_delay -min 0.5 -clock clk_core [all_outputs]

set_driving_cell -lib_cell BUF_X4 -pin Z \
  [remove_from_collection [all_inputs] [get_ports {clk clk_io}]]
set_load 0.05 [all_outputs]

# ── Design rules ─────────────────────────────────────────────
set_max_fanout     20 [all_inputs]
set_max_transition 0.2 [all_nets]
set_max_capacitance 0.1 [all_nets]

# ── Reset ────────────────────────────────────────────────────
set_ideal_network [get_ports rst_n]
set_false_path -from [get_ports rst_n]
