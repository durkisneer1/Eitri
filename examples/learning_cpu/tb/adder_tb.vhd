library ieee;
use ieee.std_logic_1164.all;
entity adder_tb is end;
architecture test of adder_tb is
    signal a, b, result : std_logic_vector(7 downto 0);
begin
    uut : entity work.adder(rtl) port map (a, b, result);
    process
    begin
        a <= x"02"; b <= x"03"; wait for 1 ns;
        assert result = x"05" report "Adder: 2 + 3 must equal 5" severity failure;
        a <= x"FF"; b <= x"01"; wait for 1 ns;
        assert result = x"00" report "Adder must wrap at 8 bits" severity failure;
        report "Adder tests passed";
        std.env.stop;
        wait;
    end process;
end;
