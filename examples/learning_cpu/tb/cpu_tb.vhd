library ieee;
use ieee.std_logic_1164.all;
use work.cpu_types.all;
entity cpu_tb is end;
architecture test of cpu_tb is
    signal clk : std_logic := '0';
    signal reset : std_logic := '1';
    signal result : byte_t;
    signal halted : std_logic;
begin
    -- Clock behavior is ordinary, manually written VHDL.
    clk <= not clk after 5 ns;
    uut : entity work.cpu(rtl) port map (clk, reset, result, halted);
    process
    begin
        wait for 12 ns;
        reset <= '0';
        wait until halted = '1';
        wait for 1 ns;
        assert result = x"06" report "CPU program should compute 1 + 2 + 3 = 6" severity failure;
        report "CPU program passed";
        std.env.stop;
        wait;
    end process;
    process
    begin
        wait for 150 ns;
        assert false report "CPU failed to halt" severity failure;
    end process;
end;
