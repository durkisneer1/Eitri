library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_types.all;
entity cpu is
    port (clk, reset : in std_logic; result : out byte_t; halted : out std_logic);
end;
architecture rtl of cpu is
    signal pc : unsigned(1 downto 0) := (others => '0');
    signal instruction, immediate : byte_t;
    signal load, enable : std_logic;
begin
    u_program : entity work.program_rom(rtl)
        port map (address => std_logic_vector(pc), instruction => instruction);
    load <= '1' when instruction(7 downto 6) = "00" else '0';
    enable <= '0' when instruction(7 downto 6) = "11" else '1';
    halted <= not enable;
    immediate <= "00" & instruction(5 downto 0);
    u_datapath : entity work.datapath(rtl)
        port map (clk => clk, reset => reset, enable => enable, load => load,
                  immediate => immediate, result => result);
    process(clk)
    begin
        if rising_edge(clk) then
            if reset = '1' then pc <= (others => '0');
            elsif enable = '1' then pc <= pc + 1;
            end if;
        end if;
    end process;
end;
