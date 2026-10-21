library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity RAM_16x32Bits is
    port (
        Clk : in STD_LOGIC;
        CS : in STD_LOGIC;
        R_W : in STD_LOGIC;
        Address : in STD_LOGIC_VECTOR(3 downto 0);
        Data_In : in STD_LOGIC_VECTOR(31 downto 0);
        Data_Out : out STD_LOGIC_VECTOR(31 downto 0)
    );
end RAM_16x32Bits;

architecture Behavioral of RAM_16x32Bits is
    type ram_array_t is array(0 to 15) of STD_LOGIC_VECTOR(31 downto 0);
    signal ram_array : ram_array_t := (others => (others => '0'));
begin

process(clk)
begin
    if rising_edge(clk) then
        Data_Out <= (others => 'Z');
        if CS = '1' then
            if R_W = '1' then
                Data_Out <= ram_array(to_integer(unsigned(Address)));
            elsif R_W = '0' then
                ram_array(to_integer(unsigned(Address))) <= Data_In;
            end if;
        end if;
    end if;
end process;
    
end Behavioral;
