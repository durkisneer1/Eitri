library ieee;
use ieee.std_logic_1164.all;
package cpu_types is
    constant DATA_WIDTH : positive := 8;
    subtype byte_t is std_logic_vector(DATA_WIDTH - 1 downto 0);
end package;
