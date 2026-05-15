# AES_CORE.sdc — sample SDC for testing the checker
# This file intentionally has a mix of good constraints and issues to check

set sdc_version 2.2
set_units -time ns -capacitance pF -resistance kOhm

# ── Clocks ───────────────────────────────────────────────────────────────────
create_clock -name clk_core -period 5.0 [get_ports clk]
create_clock -name clk_io   -period 10.0 [get_ports clk_io]

create_generated_clock -name clk_div2 \
  -source [get_ports clk] \
  -divide_by 2 \
  [get_ports clk_div2_out]

# Virtual clock for external interface
create_clock -name vclk_ext -period 8.0

set_clock_uncertainty -setup 0.15 [get_clocks clk_core]
set_clock_uncertainty -hold  0.075 [get_clocks clk_core]
set_clock_uncertainty -setup 0.20 [get_clocks clk_io]
set_clock_uncertainty -hold  0.10 [get_clocks clk_io]

set_clock_latency -source 0.4 [get_clocks {clk_core clk_io}]
set_clock_transition 0.1 [all_clocks]

# CDC — clk_core and clk_io are asynchronous
set_clock_groups -asynchronous \
  -group [get_clocks clk_core] \
  -group [get_clocks clk_io]

# ── I/O constraints ──────────────────────────────────────────────────────────
set_input_delay -max 1.2 -clock clk_core \
  [remove_from_collection [all_inputs] [get_ports {clk clk_io clk_div2_out rst_n}]]
set_input_delay -min 0.4 -clock clk_core \
  [remove_from_collection [all_inputs] [get_ports {clk clk_io clk_div2_out rst_n}]]

set_output_delay -max 1.5 -clock clk_core [all_outputs]
set_output_delay -min 0.5 -clock clk_core [all_outputs]

set_driving_cell -lib_cell BUF_X4 -pin Z \
  [remove_from_collection [all_inputs] [get_ports {clk clk_io}]]
set_load 0.05 [all_outputs]

# ── Design rule constraints ───────────────────────────────────────────────────
set_max_fanout     20 [all_inputs]
set_max_transition 0.2 [all_nets]
set_max_capacitance 0.1 [all_nets]

# ── Ideal networks ───────────────────────────────────────────────────────────
set_ideal_network [get_ports rst_n]
set_false_path -from [get_ports rst_n]

# ── DFT ──────────────────────────────────────────────────────────────────────
set_case_analysis 0 [get_ports scan_en]
set_ideal_network [get_ports scan_en]

# ── Multicycle paths ─────────────────────────────────────────────────────────
set_multicycle_path -setup 2 -from [get_cells U_CRC_REG] -to [get_cells U_CRC_OUT]
set_multicycle_path -hold  1 -from [get_cells U_CRC_REG] -to [get_cells U_CRC_OUT]
