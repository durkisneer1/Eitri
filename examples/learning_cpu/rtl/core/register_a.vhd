library ieee;
use ieee.std_logic_1164.all;
use work.cpu_types.all;
entity register_a is
    port (clk, reset, enable : in std_logic; d : in byte_t; q : out byte_t);
end;
architecture rtl of register_a is
begin
    process(clk)
    begin
        if rising_edge(clk) then
            if reset = '1' then q <= (others => '0');
            elsif enable = '1' then q <= d;
            end if;
        end if;
    end process;
end;
