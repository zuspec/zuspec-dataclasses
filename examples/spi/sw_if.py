import zuspec.dataclasses as zdc
from typing import Protocol

class SpiInitiatorOpIF(Protocol):

    async def configure(self, 
                        char_len : zdc.uint8_t,
                        divider : zdc.uint16_t,
                        tgt_sel : zdc.uint8_t): 
        """Configures the SPI Initiator
        """
        ...

    async def tx(self, data : zdc.uint128_t, slave_select: int=0) -> zdc.uint128_t: 
        """Transmits a word, returning the received data
        """
        ...

@zdc.dataclass
class SpiCtrl(zdc.PackedStruct):
    """Control and Status Register (CTRL) - Offset 0x10
    
    Bit layout (32 bits total):
    [6:0]   - CHAR_LEN: Character length (1-127 bits, 0=128 bits) - 7 bits
    [7]     - Reserved - 1 bit
    [8]     - GO_BSY: Start transfer (write 1) / Transfer in progress (read) - 1 bit
    [9]     - RX_NEG: Latch MISO on falling edge (1) or rising edge (0) - 1 bit
    [10]    - TX_NEG: Change MOSI on falling edge (1) or rising edge (0) - 1 bit
    [11]    - LSB: LSB first (1) or MSB first (0) - 1 bit
    [12]    - IE: Interrupt enable - 1 bit
    [13]    - ASS: Automatic slave select - 1 bit
    [31:14] - Reserved - 18 bits
    Total: 7+1+1+1+1+1+1+1+18 = 32 bits
    """
    char_len : zdc.uint7_t = zdc.field(default=0)      # Bits 0-6
    reserved0 : zdc.uint1_t = zdc.field(default=0)     # Bit 7
    go_bsy : zdc.uint1_t = zdc.field(default=0)        # Bit 8
    rx_neg : zdc.uint1_t = zdc.field(default=0)        # Bit 9
    tx_neg : zdc.uint1_t = zdc.field(default=0)        # Bit 10
    lsb : zdc.uint1_t = zdc.field(default=0)           # Bit 11
    ie : zdc.uint1_t = zdc.field(default=0)            # Bit 12
    ass : zdc.uint1_t = zdc.field(default=0)           # Bit 13
    # Bits 14-31 reserved (18 bits) - use combination of available types
    reserved1_low : zdc.uint8_t = zdc.field(default=0)   # Bits 14-21
    reserved1_mid : zdc.uint8_t = zdc.field(default=0)   # Bits 22-29
    reserved1_high : zdc.uint2_t = zdc.field(default=0)  # Bits 30-31


@zdc.dataclass
class SpiDivider(zdc.PackedStruct):
    """Divider Register (DIVIDER) - Offset 0x14
    
    Bit layout:
    [15:0]  - DIVIDER: Clock divider (f_sclk = f_wb_clk / (2*(DIVIDER+1)))
    [31:16] - Reserved
    """
    divider : zdc.uint16_t = zdc.field(default=0xFFFF)
    reserved : zdc.uint16_t = zdc.field(default=0)


@zdc.dataclass
class SpiSS(zdc.PackedStruct):
    """Slave Select Register (SS) - Offset 0x18
    
    Bit layout (32 bits total):
    [7:0]   - SS: Slave select bits (one bit per slave) - 8 bits
    [31:8]  - Reserved - 24 bits
    Total: 8+24 = 32 bits
    """
    ss : zdc.uint8_t = zdc.field(default=0)             # Bits 0-7
    # Bits 8-31 reserved (24 bits)
    reserved_low : zdc.uint8_t = zdc.field(default=0)   # Bits 8-15
    reserved_mid : zdc.uint8_t = zdc.field(default=0)   # Bits 16-23
    reserved_high : zdc.uint8_t = zdc.field(default=0)  # Bits 24-31


@zdc.dataclass
class SpiRegs(zdc.RegFile):
    """SPI Master Core Register File
    
    Register map:
    0x00 - Rx0/Tx0: Data receive/transmit register 0 (bits 31:0)
    0x04 - Rx1/Tx1: Data receive/transmit register 1 (bits 63:32)
    0x08 - Rx2/Tx2: Data receive/transmit register 2 (bits 95:64)
    0x0C - Rx3/Tx3: Data receive/transmit register 3 (bits 127:96)
    0x10 - CTRL: Control and status register
    0x14 - DIVIDER: Clock divider register
    0x18 - SS: Slave select register
    
    Note: Rx and Tx registers share the same flip-flops. Reading returns
    received data, writing sets transmit data.
    """
    # Data registers (Rx/Tx share same address space)
    data0 : zdc.Reg[zdc.uint32_t] = zdc.field()  # Offset 0x00
    data1 : zdc.Reg[zdc.uint32_t] = zdc.field()  # Offset 0x04
    data2 : zdc.Reg[zdc.uint32_t] = zdc.field()  # Offset 0x08
    data3 : zdc.Reg[zdc.uint32_t] = zdc.field()  # Offset 0x0C
    
    # Control and configuration registers
    ctrl : zdc.Reg[SpiCtrl] = zdc.field()        # Offset 0x10
    divider : zdc.Reg[SpiDivider] = zdc.field()  # Offset 0x14
    ss : zdc.Reg[SpiSS] = zdc.field()            # Offset 0x18



@zdc.dataclass
class ISpiInitiatorPV(Protocol):
    regs : SpiRegs = zdc.field()
    irq : zdc.Event = zdc.field()


