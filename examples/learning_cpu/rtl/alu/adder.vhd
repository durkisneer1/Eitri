library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity adder is
    generic (WIDTH : positive := 8);
    port (a, b : in std_logic_vector(WIDTH - 1 downto 0);
          result : out std_logic_vector(WIDTH - 1 downto 0));
end;
architecture rtl of adder is
begin
    result <= std_logic_vector(unsigned(a) + unsigned(b));
end;
