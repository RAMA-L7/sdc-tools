# V1 Variable definitions — broad static path wildcard, 4-cycle multicycle
set CYCLE 4
set STATIC_PINS [get_pins -hier * -filter "full_name=~*static_inst*"]
set PWR_PINS [get_pins -hier * -filter "full_name=~*pwr_ctrl*"]
