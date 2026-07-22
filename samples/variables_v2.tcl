# V2 Variable definitions — narrower static path wildcard, 2-cycle multicycle
set CYCLE 2
set STATIC_PINS [get_pins -hier * -filter "full_name=~*static_inst1*"]
set PWR_PINS [get_pins -hier * -filter "full_name=~*pwr_ctrl*"]
