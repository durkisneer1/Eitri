library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity MUX4to1_32Bits is
    port (
        S : in STD_LOGIC_VECTOR(1 downto 0);
        A : in STD_LOGIC_VECTOR(31 downto 0);
        B : in STD_LOGIC_VECTOR(31 downto 0);
        C : in STD_LOGIC_VECTOR(31 downto 0);
        D : in STD_LOGIC_VECTOR(31 downto 0);
        Y : out STD_LOGIC_VECTOR(31 downto 0)
    );
end MUX4to1_32Bits;

architecture Behavioral of MUX4to1_32Bits is
    -- Declare internal signals here.
begin

process(all) begin
    case S is
        when "00" =>
            Y <= A;
        when "01" =>
            Y <= B;
        when "10" =>
            Y <= C;
        when "11" =>
            Y <= D;
        when others =>
            Y <= (others => 'X');
    end case;
end process;

end Behavioral;
