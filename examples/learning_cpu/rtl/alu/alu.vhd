library ieee;
use ieee.std_logic_1164.all;
use work.cpu_types.all;
entity alu is
    port (a, b : in byte_t; load : in std_logic; result : out byte_t);
end;
architecture rtl of alu is
    signal sum : byte_t;
begin
    u_add : entity work.adder(rtl)
        generic map (WIDTH => DATA_WIDTH)
        port map (a => a, b => b, result => sum);
    result <= b when load = '1' else sum;
end;
