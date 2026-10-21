library ieee;
use ieee.std_logic_1164.all;
use work.cpu_types.all;
entity datapath is
    port (clk, reset, enable, load : in std_logic; immediate : in byte_t; result : out byte_t);
end;
architecture rtl of datapath is
    signal accumulator, next_value : byte_t;
begin
    u_alu : entity work.alu(rtl)
        port map (a => accumulator, b => immediate, load => load, result => next_value);
    u_accumulator : entity work.register_a(rtl)
        port map (clk => clk, reset => reset, enable => enable, d => next_value, q => accumulator);
    result <= accumulator;
end;
