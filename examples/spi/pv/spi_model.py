#****************************************************************************
# SPI Master Core Protocol-Level Model
# Based on OpenCores SPI Master Core Specification Rev 0.6
#****************************************************************************

import sys
sys.path.insert(0, '../../../src')

import zuspec.dataclasses as zdc
from typing import Protocol

# =============================================================================
# Register Type Definitions (Packed Structs)
# =============================================================================

@zdc.dataclass
class SpiCtrl(zdc.PackedStruct):
    """Control and Status Register [CTRL] - Offset 0x10
    
    Bit layout (LSB to MSB for packed struct):
    - CHAR_LEN[6:0]: Character length (0x01-0x7f bits, 0x00=128 bits)
    - Reserved[7]: Reserved bit
    - GO_BSY[8]: Transfer in progress / start transfer
    - Rx_NEG[9]: Latch MISO on falling edge
    - Tx_NEG[10]: Change MOSI on falling edge
    - LSB[11]: LSB first when set
    - IE[12]: Interrupt enable
    - ASS[13]: Auto slave select
    - Reserved[31:14]: Reserved bits
    """
    char_len : zdc.uint7_t = zdc.field()      # Bits [6:0]: Transfer character length
    reserved0 : zdc.uint1_t = zdc.field()     # Bit [7]: Reserved
    go_bsy : zdc.uint1_t = zdc.field()        # Bit [8]: Go/Busy flag
    rx_neg : zdc.uint1_t = zdc.field()        # Bit [9]: Rx on negative edge
    tx_neg : zdc.uint1_t = zdc.field()        # Bit [10]: Tx on negative edge
    lsb : zdc.uint1_t = zdc.field()           # Bit [11]: LSB first
    ie : zdc.uint1_t = zdc.field()            # Bit [12]: Interrupt enable
    ass : zdc.uint1_t = zdc.field()           # Bit [13]: Auto slave select
    reserved1 : zdc.uint32_t = zdc.field()    # Bits [31:14]: Reserved (using 32 for padding)


@zdc.dataclass
class SpiDivider(zdc.PackedStruct):
    """Divider Register [DIVIDER] - Offset 0x14
    
    Reset value: 0x0000ffff
    f_sclk = f_wb_clk / ((DIVIDER + 1) * 2)
    """
    divider : zdc.uint16_t = zdc.field()      # Bits [15:0]: Clock divider value
    reserved : zdc.uint16_t = zdc.field()     # Bits [31:16]: Reserved


@zdc.dataclass
class SpiSS(zdc.PackedStruct):
    """Slave Select Register [SS] - Offset 0x18
    
    Controls which slave device is selected.
    """
    ss : zdc.uint8_t = zdc.field()            # Bits [7:0]: Slave select lines
    reserved : zdc.uint32_t = zdc.field()     # Bits [31:8]: Reserved (using 32 for padding)


# =============================================================================
# Register File Definition
# =============================================================================

@zdc.dataclass
class SpiRegs(zdc.RegFile):
    """SPI Master Core Register File
    
    Register Map:
    - 0x00: Rx0/Tx0 - Data register 0 (shared read/write)
    - 0x04: Rx1/Tx1 - Data register 1 (shared read/write)  
    - 0x08: Rx2/Tx2 - Data register 2 (shared read/write)
    - 0x0C: Rx3/Tx3 - Data register 3 (shared read/write)
    - 0x10: CTRL    - Control and status register
    - 0x14: DIVIDER - Clock divider register
    - 0x18: SS      - Slave select register
    
    Note: Rx and Tx registers share the same flip-flops
    """
    # Data registers (Rx/Tx share same FFs - write to Tx, read from Rx)
    data0 : zdc.Reg[zdc.uint32_t] = zdc.field()    # Offset 0x00
    data1 : zdc.Reg[zdc.uint32_t] = zdc.field()    # Offset 0x04
    data2 : zdc.Reg[zdc.uint32_t] = zdc.field()    # Offset 0x08
    data3 : zdc.Reg[zdc.uint32_t] = zdc.field()    # Offset 0x0C
    
    # Control registers
    ctrl : zdc.Reg[SpiCtrl] = zdc.field()          # Offset 0x10
    divider : zdc.Reg[SpiDivider] = zdc.field()    # Offset 0x14
    ss : zdc.Reg[SpiSS] = zdc.field()              # Offset 0x18


# =============================================================================
# SPI Data Interface (for sending/receiving bytes)
# =============================================================================

class SpiDataIF(Protocol):
    """Interface for SPI data transfer operations.
    
    Provides a byte-level interface to the SPI master.
    """
    async def send_byte(self, data: int, slave_select: int = 0) -> int:
        """Send a byte and receive a byte simultaneously (full duplex).
        
        Args:
            data: Byte to transmit (0-255)
            slave_select: Which slave to select (0-7)
            
        Returns:
            Received byte (0-255)
        """
        ...
    
    async def is_busy(self) -> bool:
        """Check if a transfer is in progress."""
        ...


# =============================================================================
# SPI Master Component
# =============================================================================

@zdc.dataclass
class SpiMaster(zdc.Component):
    """SPI Master Core Component
    
    Provides:
    - Register interface for configuration and status
    - Data interface for byte-level transfers
    """
    # Register file
    regs : SpiRegs = zdc.field()
    
    # Export for data interface
    data_if : SpiDataIF = zdc.export()
    
    def __post_init__(self):
        # Initialize divider to reset value (0xFFFF)
        pass
    
    async def send_byte(self, data: int, slave_select: int = 0) -> int:
        """Send a byte over SPI.
        
        This method:
        1. Writes the data to Tx register
        2. Sets up control register (8-bit transfer, etc.)
        3. Sets slave select
        4. Starts the transfer
        5. Waits for completion
        6. Returns received data
        
        Args:
            data: Byte to transmit (0-255)
            slave_select: Which slave to select (0-7)
            
        Returns:
            Received byte (0-255)
        """
        # Write transmit data to data0 register
        await self.regs.data0.write(data & 0xFF)
        
        # Set slave select (write as integer)
        ss_val = (1 << slave_select) & 0xFF
        await self.regs.ss.write(ss_val)
        
        # Configure control register for 8-bit transfer and start
        # Bit layout: char_len[6:0]=8, go_bsy[8]=1, tx_neg[10]=1, ass[13]=1
        ctrl_val = 8 | (1 << 8) | (1 << 10) | (1 << 13)
        await self.regs.ctrl.write(ctrl_val)
        
        # Wait for transfer to complete (poll GO_BSY bit)
        while True:
            ctrl_read = await self.regs.ctrl.read()
            if ctrl_read.go_bsy == 0:
                break
            await self.wait(zdc.Time.ns(10))  # Small delay before checking again
        
        # Read received data
        rx_data = await self.regs.data0.read()
        return rx_data & 0xFF
    
    async def is_busy(self) -> bool:
        """Check if a transfer is in progress."""
        ctrl = await self.regs.ctrl.read()
        return ctrl.go_bsy == 1
    
    @zdc.process
    async def _transfer_engine(self):
        """Simulates the SPI transfer engine.
        
        Monitors the GO_BSY bit and simulates transfer completion.
        In a real implementation, this would interact with the 
        serial interface.
        """
        while True:
            ctrl = await self.regs.ctrl.read()
            
            if ctrl.go_bsy == 1:
                # Calculate transfer time based on character length and divider
                divider_reg = await self.regs.divider.read()
                divider_val = divider_reg.divider if hasattr(divider_reg, 'divider') else divider_reg
                char_len = ctrl.char_len if ctrl.char_len > 0 else 128
                
                # Simplified timing: assume 1 clock per bit at divider rate
                # In reality: f_sclk = f_wb_clk / ((DIVIDER + 1) * 2)
                # For simulation, we use a simplified delay
                transfer_time_ns = char_len * 10  # 10ns per bit (simplified)
                
                await self.wait(zdc.Time.ns(transfer_time_ns))
                
                # Transfer complete - clear GO_BSY by reading current value and clearing bit 8
                # Read current ctrl value, clear go_bsy bit, write back
                ctrl_int = await self.regs.ctrl.read()
                # Convert to int, clear bit 8, write back
                ctrl_as_int = (ctrl_int.char_len | 
                              (ctrl_int.reserved0 << 7) |
                              (0 << 8) |  # go_bsy = 0
                              (ctrl_int.rx_neg << 9) |
                              (ctrl_int.tx_neg << 10) |
                              (ctrl_int.lsb << 11) |
                              (ctrl_int.ie << 12) |
                              (ctrl_int.ass << 13))
                await self.regs.ctrl.write(ctrl_as_int)
            else:
                # No transfer in progress, wait a bit before checking again
                await self.wait(zdc.Time.ns(10))


# =============================================================================
# Helper function to create a configured SPI master
# =============================================================================

def create_spi_master(clock_freq_mhz: float = 100.0, spi_freq_mhz: float = 10.0) -> SpiMaster:
    """Create and configure an SPI master.
    
    Args:
        clock_freq_mhz: System clock frequency in MHz
        spi_freq_mhz: Desired SPI clock frequency in MHz
        
    Returns:
        Configured SpiMaster component
    """
    spi = SpiMaster()
    
    # Calculate divider: f_sclk = f_wb_clk / ((DIVIDER + 1) * 2)
    # DIVIDER = (f_wb_clk / (2 * f_sclk)) - 1
    divider = int((clock_freq_mhz / (2 * spi_freq_mhz)) - 1)
    divider = max(0, min(0xFFFF, divider))  # Clamp to valid range
    
    return spi
