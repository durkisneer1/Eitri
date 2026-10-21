library ieee;
use ieee.std_logic_1164.all;
use work.cpu_types.all;
entity alu_tb is end;
architecture test of alu_tb is
    signal a, b, result : byte_t;
    signal load : std_logic;
begin
    uut : entity work.alu(rtl) port map (a, b, load, result);
    process
    begin
        a <= x"02"; b <= x"03"; load <= '1'; wait for 1 ns;
        assert result = x"03" report "LOAD must select the immediate" severity failure;
        load <= '0'; wait for 1 ns;
        assert result = x"05" report "ADD must sum the operands" severity failure;
        std.env.stop;
        wait;
    end process;
end;
