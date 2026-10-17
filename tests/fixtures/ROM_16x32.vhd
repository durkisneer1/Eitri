library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity ROM_16x32 is
    port (
        Clk      : in  STD_LOGIC;
        CS       : in  STD_LOGIC;
        Address  : in  STD_LOGIC_VECTOR(3 downto 0);
        Data_Out : out STD_LOGIC_VECTOR(31 downto 0)
    );
end ROM_16x32;

architecture bamboo of ROM_16x32 is
    type mem_array_t is array (0 to 15) of STD_LOGIC_VECTOR(31 downto 0);

    constant ROM_Bank0 : mem_array_t := (
         0 => x"DEADBEEF",
         1 => x"CAFEBABE",
         2 => x"DEADFEED",
         3 => x"BEEFCAFE",
         4 => x"12345678",
         5 => x"ABCDEF01",
         6 => x"F00DFACE",
         7 => x"C0FFEE42",
         8 => x"FEEDC0DE",
         9 => x"FEEDC0DE",
        10 => x"BAADF00D",
        11 => x"CAFED00D",
        12 => x"DEADC0DE",
        13 => x"FACADE00",
        14 => x"B16B00B5",
        15 => x"DEADD00D"
    );

    signal tmp_data_out : STD_LOGIC_VECTOR(31 downto 0) := (others => 'Z');
begin
    rom_read : process (Clk)
    begin
        if rising_edge(Clk) then
            if CS = '1' then
                tmp_data_out <= ROM_Bank0(to_integer(unsigned(Address)));
            elsif CS = '0' then
                tmp_data_out <= (others => 'Z');
            end if;
        end if;
    end process rom_read;

    Data_Out <= tmp_data_out;
end bamboo;
