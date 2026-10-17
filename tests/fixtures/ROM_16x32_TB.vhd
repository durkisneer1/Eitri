library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity ROM_16x32_TB is
end ROM_16x32_TB;

architecture Behavioral of ROM_16x32_TB is
    component ROM_16x32 is
        port (
            Clk      : in  STD_LOGIC;
            CS       : in  STD_LOGIC;
            Address  : in  STD_LOGIC_VECTOR(3 downto 0);
            Data_Out : out STD_LOGIC_VECTOR(31 downto 0)
        );
    end component;

    signal Clk      : STD_LOGIC := '0';
    signal CS       : STD_LOGIC;
    signal Address  : STD_LOGIC_VECTOR(3 downto 0);
    signal Data_Out : STD_LOGIC_VECTOR(31 downto 0);

    constant CLK_PERIOD : time := 20 ns;
begin
    uut : ROM_16x32
        port map (
            Clk      => Clk,
            CS       => CS,
            Address  => Address,
            Data_Out => Data_Out
        );

    clk_proc : process
    begin
        Clk <= '0';
        wait for CLK_PERIOD / 2;
        Clk <= '1';
        wait for CLK_PERIOD / 2;
    end process;

    stimulus : process
    begin
        CS <= '1';
        Address <= x"0";
        wait for CLK_PERIOD;

        CS <= '0';
        Address <= x"0";
        wait for CLK_PERIOD;

        CS <= '1';
        Address <= x"1";
        wait for CLK_PERIOD;

        CS <= '1';
        Address <= x"2";
        wait for CLK_PERIOD;

        CS <= '1';
        Address <= x"3";
        wait for CLK_PERIOD;

        CS <= '0';
        Address <= x"4";
        wait for CLK_PERIOD;

        CS <= '1';
        Address <= x"E";
        wait for CLK_PERIOD;

        CS <= '1';
        Address <= x"F";
        wait for CLK_PERIOD;

        CS <= '0';
        Address <= x"F";
        wait for CLK_PERIOD;

        wait;
    end process stimulus;
end Behavioral;
