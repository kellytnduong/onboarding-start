/*
 * Copyright (c) 2025 Kelly Duong
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input  wire       clk,      // clock
    input  wire       rst_n,    // reset_n - low to reset

    //Registers
    output  reg [7:0] en_reg_out_7_0,
    output  reg [7:0] en_reg_out_15_8,
    output  reg [7:0] en_reg_pwm_7_0,
    output  reg [7:0] en_reg_pwm_15_8,
    output  reg [7:0] pwm_duty_cycle,

    input  wire       spi_sclk,
    input  wire       spi_copi,
    input  wire       spi_cs
);

    localparam max_address = 4'h4;          // max_address size of 0x04
    reg [4:0] bit_count;                    // max 16 bit capture
    reg [15:0] spi_shift;                   // register to store shifted bits (16 bits)

    reg transaction_ready;                  // flag to signal a ready transaction
    reg transaction_processed;               // flag to signal a complete transaction

    reg rw_bit;
    reg [6:0] reg_address;
    reg [7:0] data;
    
    //Sync with 3 flip flops to avoid metastability
    reg spi_sclk_curr;
    reg spi_sclk_prev0;
    reg spi_sclk_prev1;

    reg spi_copi_curr;
    reg spi_copi_prev0;
    reg spi_copi_prev1;

    reg spi_cs_curr;
    reg spi_cs_prev0;
    reg spi_cs_prev1;
    
    // Rising edge data sampling
    wire spi_sclk_rising = ~spi_sclk_prev0 & spi_sclk_curr;
    wire spi_sclk_falling = spi_sclk_prev0 & ~spi_sclk_curr;

    // Falling edge data shifting
    wire spi_cs_rising = ~spi_cs_prev0 & spi_cs_curr;
    wire spi_cs_falling = spi_cs_prev0 & ~spi_cs_curr;

    wire _unused = &{spi_sclk_falling, spi_cs_rising};

    // Updating sampled inputs
    always @(posedge clk or negedge rst_n) begin 
        if (!rst_n) begin  
            spi_sclk_curr <= 0;
            spi_copi_curr <= 0;
            spi_cs_curr <= 0;
        end else begin
            spi_sclk_curr <= spi_sclk;
            spi_copi_curr <= spi_copi;
            spi_cs_curr <= spi_cs;
        end
    end

    // Signal synchronization
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_sclk_prev0 <= 0;
            spi_sclk_prev1 <= 0;
            spi_copi_prev0 <= 0;
            spi_copi_prev1 <= 0;
            spi_cs_prev0 <= 0;
            spi_cs_prev1 <= 0;
        end else begin
            spi_sclk_prev0 <= spi_sclk_curr;
            spi_sclk_prev1 <= spi_sclk_prev0;

            spi_copi_prev0 <= spi_copi_curr;
            spi_copi_prev1 <= spi_copi_prev0;

            spi_cs_prev0 <= spi_cs_curr;
            spi_cs_prev1 <= spi_cs_prev0;
        end
    end
           
    // Shifting to capture bits on active transaction
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_shift <= 16'd0;
            bit_count <= 0;
        end else if (spi_cs_prev0 == 1'b0) begin
            if (spi_sclk_rising) begin
                spi_shift <= {spi_shift[14:0], spi_copi_prev1};
                bit_count <= bit_count + 1;
            end
        end else begin
            bit_count <= 0;
        end
    end

    // Identifies complete (16 bit filled) transaction
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            transaction_ready <= 1'b0;
        end else if (spi_cs_rising) begin 
            if (bit_count == 16) begin
                transaction_ready <= 1'b1;
            end
        end else if (transaction_processed) begin
            transaction_ready <= 1'b0;
        end
    end

    // Process transaction
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            transaction_processed <= 1'b0;
            rw_bit <= 0;
            reg_address <= 7'd0;
            data <= 8'd0;

            en_reg_out_7_0 <= 0;
            en_reg_out_15_8 <= 0;
            en_reg_pwm_7_0 <= 0;
            en_reg_pwm_15_8 <= 0;
            pwm_duty_cycle <= 0;

        end else if (transaction_ready && !transaction_processed) begin
            transaction_processed <= 1'b1;

            rw_bit <= spi_shift[15];
            reg_address <= spi_shift[14:8];
            data <= spi_shift[7:0];

            if (spi_shift[15] == 1) begin
                case (spi_shift[14:8])
                    7'h00:
                    en_reg_out_7_0 <= spi_shift[7:0];
                    7'h01:
                    en_reg_out_15_8 <= spi_shift[7:0];
                    7'h02:
                    en_reg_pwm_7_0 <= spi_shift[7:0];
                    7'h03:
                    en_reg_pwm_15_8 <= spi_shift[7:0];
                    7'h04:
                    pwm_duty_cycle <= spi_shift[7:0];
                    default: ;
                endcase
            end
        end else if (!transaction_ready && transaction_processed) begin
            transaction_processed <= 1'b0;
        end
    end
endmodule
