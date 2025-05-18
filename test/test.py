# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test") 

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")


async def receive_pwm_sample(dut, signal, channel):
    period = 100 # in ns
    max_time = 4000000 # in ns
    cycles = 2 #number of cycles to wait

    num_of_rising = []
    num_of_falling = []
    high_times = []
    prev_edge = (int(signal.value) >> channel) & 0x1

    last_high = 0
    last_low = 0
    
    start_time = cocotb.utils.get_sim_time(units="ns")

    while len(num_of_rising) <= cycles:
        await ClockCycles(dut.clk, 1)
        
        curr_time = cocotb.utils.get_sim_time(units="ns")
        curr_edge = (int(signal.value) >> channel) & 0x1

        #If signal is stuck
        if (curr_time - start_time) > max_time:
            if (curr_edge == 1):
                return 1, 0
            elif (curr_edge == 0):
                return 0, 0
            
        #Otherwise, check for rising edge/falling edge and append
        if ((curr_edge == 1) and (prev_edge == 0)):
            num_of_rising.append(curr_time)
            last_high = curr_time
        elif ((curr_edge == 0) and (prev_edge == 1)):
            num_of_falling.append(curr_time)
            if (last_high != 0):
                high_times.append(curr_time - last_high)
            last_low = curr_time

        prev_edge = curr_edge

    periods = []
    for t1, t2 in zip(num_of_rising, num_of_rising[1:]):
        periods.append(t2 - t1)

    if (high_times.empty()):
        avg_high_times = 0
    else:
        avg_high_times = sum(high_times)/len(high_times)

    if (periods.empty()):
        avg_period = 0
    else:
        avg_period = sum(periods)/len(periods)

    if (avg_period > 0):
        frequency = 1E9/avg_period
        duty = avg_high_times/avg_period
    else:
        frequency = 0
        duty = 0

    return duty, frequency

@cocotb.test()
async def test_pwm_freq(dut):
    dut._log.info("Start PWM Frequency test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    await send_spi_transaction(dut, 1, 0x04, 0x80) # 50% duty cycle (128 in hex for 128/256 x 100% = 50%)
    
    dut._log.info("Testing ui_out frequencies (Output & PWM channels 0-7)")
    for i in range(8):
        dut._log.info("Writing to Output channel %d", i)
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, i)

        dut._log.info("Writing to PWM channel %d", i)
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, i)

        dut._log.info("Reading PWM channel %d", i)
        duty, frequency = await receive_pwm_sample(dut, dut.uo_out, channel=i)


        assert 2970 <= frequency <= 3030, f"Expected frequency around 3000Hz +- 1% on channel {i}, got {frequency}"
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0)
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0)

    dut._log.info("Testing uio_out frequencies (Output & PWM channels 8-15)")
    for i in range(8):
        dut._log.info("Writing to Output channel %d", i+8)
        ui_in_val = await send_spi_transaction(dut, 1, 0x01, i)
        
        dut._log.info("Writing to PWM channel %d", i+8)
        ui_in_val = await send_spi_transaction(dut, 1, 0x03, i)

        dut._log.info("Reading PWM channel %d", i+8)
        duty, frequency = await receive_pwm_sample(dut, dut.uio_out, channel=i)

        assert 2970 <= frequency <= 3030, f"Expected frequency around 3000Hz +- 1% on channel {i+8}, got {frequency}"
        ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0)
        ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0)

    dut._log.info("PWM Frequency test completed successfully")


@cocotb.test()
async def test_pwm_duty(dut):
    dut._log.info("Start PWM Duty test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut.log.info("Testing ui_out duty cycle (Output & PWM channels 0-7)")
    for i in range(8):
        dut._log.info("Writing to Output channel %d", i)
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, i)

        dut._log.info("Writing to PWM channel %d", i)
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, i)

        # 0% Duty cycle
        await send_spi_transaction(dut, 1, 0x04, 0x00)
        await ClockCycles(dut.clk, 10000)
        duty, frequency = await receive_pwm_sample(dut, dut.uo_out, channel=i)
        assert duty == 0, f"Expected 0% duty cycle on channel {i}, got {duty}"

        # 50% Duty cycle
        await send_spi_transaction(dut, 1, 0x04, 0x80)
        await ClockCycles(dut.clk, 10000)
        duty, frequency = await receive_pwm_sample(dut, dut.uo_out, channel=i)
        assert 0.499 <= duty <= 0.501, f"Expected 50% duty cycle on channel {i}, got {duty}"

        # 100% Duty cycle
        await send_spi_transaction(dut, 1, 0x04, 0xFF)
        await ClockCycles(dut.clk, 10000)
        duty, frequency = await receive_pwm_sample(dut, dut.uo_out, channel=i)
        assert duty == 1, f"Expected 100% duty cycle on channel {i}, got {duty}"

    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0)

    dut.log.info("Testing ui_out duty cycle (Output & PWM channels 8-15)")
    for i in range(8):
        dut._log.info("Writing to Output channel %d", i+8)
        ui_in_val = await send_spi_transaction(dut, 1, 0x01, i)

        dut._log.info("Writing to PWM channel %d", i+8)
        ui_in_val = await send_spi_transaction(dut, 1, 0x03, i)

        # 0% Duty cycle
        await send_spi_transaction(dut, 1, 0x04, 0x00)
        duty, frequency = await receive_pwm_sample(dut, dut.uio_out, channel=i)
        assert duty == 0, f"Expected 0% duty cycle on channel {i+8}, got {duty}"

        # 50% Duty cycle
        await send_spi_transaction(dut, 1, 0x04, 0x80)
        duty, frequency = await receive_pwm_sample(dut, dut.uio_out, channel=i)
        assert 0.499 <= duty <= 0.501, f"Expected 50% duty cycle on channel {i+8}, got {duty}"

        # 100% Duty cycle
        await send_spi_transaction(dut, 1, 0x04, 0xFF)
        duty, frequency = await receive_pwm_sample(dut, dut.uio_out, channel=i)
        assert duty == 1, f"Expected 100% duty cycle on channel {i+8}, got {duty}"

    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0)
    ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0)
      
    dut._log.info("PWM Duty Cycle test completed successfully")
