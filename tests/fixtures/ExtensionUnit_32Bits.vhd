library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity ExtensionUnit_32Bits is
    port (
        Sign_Ctrl : in STD_LOGIC;
        Data_In : in STD_LOGIC_VECTOR(15 downto 0);
        Data_Out : out STD_LOGIC_VECTOR(31 downto 0)
    );
end ExtensionUnit_32Bits;

architecture Behavioral of ExtensionUnit_32Bits is
    -- Declare internal signals here.
begin

process(all) begin
    case Sign_Ctrl is
        when '0' =>
            Data_Out <= x"0000" & Data_In;
        when '1' =>
            Data_Out <= (31 downto 16 => Data_In(15)) & Data_In;
        when others =>
            Data_Out <= (others => 'X');
    end case;
end process;

end Behavioral;
