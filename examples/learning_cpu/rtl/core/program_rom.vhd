library ieee;
use ieee.std_logic_1164.all;
use work.cpu_types.all;
entity program_rom is
    port (address : in std_logic_vector(1 downto 0); instruction : out byte_t);
end;
architecture rtl of program_rom is
begin
    -- 00 = load immediate, 01 = add immediate, 11 = halt.
    with address select instruction <=
        "00000001" when "00", -- LOAD 1
        "01000010" when "01", -- ADD 2
        "01000011" when "10", -- ADD 3
        "11000000" when others;
end;
