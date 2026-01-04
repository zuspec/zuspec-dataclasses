# SPI Master Core Programmer's Guide

## 1. Introduction

The OpenCores SPI Master Core is a WISHBONE-compliant synchronous serial controller that provides a flexible interface for communicating with SPI and Microwire/Plus compatible devices. This guide provides detailed programming instructions for embedded software developers.

### 1.1 Key Features

- Full duplex synchronous serial data transfer
- Variable transfer word length: 1 to 128 bits
- MSB or LSB first data transfer
- Configurable clock polarity and phase (supports all SPI modes)
- 8 independent slave select lines with automatic or manual control
- Programmable clock divider
- Interrupt support for transfer completion

### 1.2 Document Conventions

- Register addresses are relative to the SPI core base address
- Bit numbering starts at 0 (LSB)
- `[n:m]` notation indicates bit range from bit n down to bit m
- Code examples use C-style pseudocode

---

## 2. Register Map

The SPI Master Core contains seven 32-bit registers. All register accesses must be 32-bit aligned.

| Address | Name    | Access | Description |
|---------|---------|--------|-------------|
| 0x00    | Rx0/Tx0 | R/W    | Data register 0 (bits 31:0) |
| 0x04    | Rx1/Tx1 | R/W    | Data register 1 (bits 63:32) |
| 0x08    | Rx2/Tx2 | R/W    | Data register 2 (bits 95:64) |
| 0x0C    | Rx3/Tx3 | R/W    | Data register 3 (bits 127:96) |
| 0x10    | CTRL    | R/W    | Control and status register |
| 0x14    | DIVIDER | R/W    | Clock divider register |
| 0x18    | SS      | R/W    | Slave select register |

> **Important:** The Rx and Tx registers share the same physical flip-flops. Reading returns received data; writing sets transmit data. Data received in one transfer will be transmitted in the next transfer if Tx is not rewritten.

### 2.1 Data Registers (Rx0-Rx3 / Tx0-Tx3)

**Address:** 0x00, 0x04, 0x08, 0x0C  
**Reset Value:** 0x00000000

| Bits | Access | Description |
|------|--------|-------------|
| 31:0 | R/W    | Transmit/Receive data |

The number of data registers used depends on the configured character length:

| Character Length | Registers Used |
|-----------------|----------------|
| 1-32 bits       | Tx0/Rx0 only |
| 33-64 bits      | Tx0/Rx0, Tx1/Rx1 |
| 65-96 bits      | Tx0/Rx0, Tx1/Rx1, Tx2/Rx2 |
| 97-128 bits     | All four registers |

### 2.2 Control and Status Register (CTRL)

**Address:** 0x10  
**Reset Value:** 0x00000000

| Bit(s) | Name     | Access | Description |
|--------|----------|--------|-------------|
| 6:0    | CHAR_LEN | R/W    | Character length (number of bits to transfer) |
| 7      | Reserved | R      | Reserved, reads as 0 |
| 8      | GO_BSY   | R/W    | Go/Busy status bit |
| 9      | Rx_NEG   | R/W    | Receive on negative edge |
| 10     | Tx_NEG   | R/W    | Transmit on negative edge |
| 11     | LSB      | R/W    | LSB first mode |
| 12     | IE       | R/W    | Interrupt enable |
| 13     | ASS      | R/W    | Automatic slave select |
| 31:14  | Reserved | R      | Reserved, reads as 0 |

#### CHAR_LEN Field

Specifies the number of bits to transfer:
- `0x01` = 1 bit
- `0x02` = 2 bits
- ...
- `0x7F` = 127 bits
- `0x00` = 128 bits

#### GO_BSY Bit

- **Write 1:** Starts a new transfer
- **Write 0:** No effect
- **Read 1:** Transfer in progress
- **Read 0:** Transfer complete or idle

> **Note:** All other registers must be configured before writing 1 to GO_BSY. Register writes during an active transfer are ignored.

#### Rx_NEG and Tx_NEG Bits

These bits control the clock edge used for data sampling and shifting:

| Tx_NEG | Rx_NEG | MOSI Changes | MISO Sampled |
|--------|--------|--------------|--------------|
| 0      | 0      | Rising edge  | Rising edge  |
| 0      | 1      | Rising edge  | Falling edge |
| 1      | 0      | Falling edge | Rising edge  |
| 1      | 1      | Falling edge | Falling edge |

#### LSB Bit

- **0:** MSB first (standard SPI mode)
- **1:** LSB first

#### IE Bit

- **0:** Interrupt disabled
- **1:** Interrupt enabled; `wb_int_o` asserts after transfer completion

The interrupt is cleared by any read or write to any SPI register.

#### ASS Bit

- **0:** Manual slave select control
- **1:** Automatic slave select control

### 2.3 Divider Register (DIVIDER)

**Address:** 0x14  
**Reset Value:** 0x0000FFFF

| Bit(s) | Name     | Access | Description |
|--------|----------|--------|-------------|
| 15:0   | DIVIDER  | R/W    | Clock divider value |
| 31:16  | Reserved | R      | Reserved, reads as 0 |

The SPI clock frequency is calculated as:

$$f_{sclk} = \frac{f_{wb\_clk}}{2 \times (DIVIDER + 1)}$$

**Example calculations:**

| System Clock | DIVIDER | SPI Clock |
|-------------|---------|-----------|
| 100 MHz     | 0       | 50 MHz    |
| 100 MHz     | 1       | 25 MHz    |
| 100 MHz     | 4       | 10 MHz    |
| 100 MHz     | 49      | 1 MHz     |
| 100 MHz     | 0xFFFF  | ~763 Hz   |

### 2.4 Slave Select Register (SS)

**Address:** 0x18  
**Reset Value:** 0x00000000

| Bit(s) | Name     | Access | Description |
|--------|----------|--------|-------------|
| 7:0    | SS       | R/W    | Slave select bits |
| 31:8   | Reserved | R      | Reserved, reads as 0 |

Each bit corresponds to one `ss_pad_o` output line (active low):

| Bit | Signal |
|-----|--------|
| 0   | ss_pad_o[0] |
| 1   | ss_pad_o[1] |
| ... | ... |
| 7   | ss_pad_o[7] |

---

## 3. Configuring the SPI Core

Before performing transfers, the SPI core must be properly configured. This section describes the required configuration steps.

### 3.1 Setting the Clock Frequency

The SPI clock frequency must be compatible with the target slave device. Configure the DIVIDER register based on your system clock and desired SPI clock:

```c
// Calculate divider for desired SPI clock
// divider = (system_clock / (2 * spi_clock)) - 1
uint16_t divider = (SYSTEM_CLOCK_HZ / (2 * SPI_CLOCK_HZ)) - 1;

// Write to DIVIDER register
SPI_DIVIDER = divider;
```

**Example:** For a 100 MHz system clock and 1 MHz SPI clock:
```c
uint16_t divider = (100000000 / (2 * 1000000)) - 1;  // divider = 49
SPI_DIVIDER = 49;
```

### 3.2 Setting the Character Length

Configure the number of bits per transfer using the CHAR_LEN field:

```c
// Read current CTRL value
uint32_t ctrl = SPI_CTRL;

// Clear CHAR_LEN field and set new value
ctrl = (ctrl & ~0x7F) | (char_len & 0x7F);

// Write back (ensure GO_BSY is 0)
ctrl &= ~(1 << 8);  // Clear GO_BSY
SPI_CTRL = ctrl;
```

Common character lengths:
- 8 bits: `CHAR_LEN = 0x08`
- 16 bits: `CHAR_LEN = 0x10`
- 32 bits: `CHAR_LEN = 0x20`

### 3.3 Configuring SPI Mode

SPI has four standard modes defined by clock polarity (CPOL) and clock phase (CPHA). Configure using Tx_NEG and Rx_NEG:

| SPI Mode | CPOL | CPHA | Tx_NEG | Rx_NEG | Description |
|----------|------|------|--------|--------|-------------|
| 0        | 0    | 0    | 0      | 1      | MOSI: rising edge, MISO: falling edge |
| 1        | 0    | 1    | 1      | 0      | MOSI: falling edge, MISO: rising edge |
| 2        | 1    | 0    | 1      | 0      | MOSI: falling edge, MISO: rising edge |
| 3        | 1    | 1    | 0      | 1      | MOSI: rising edge, MISO: falling edge |

> **Note:** The core does not directly support CPOL (idle clock state). The mapping above assumes CPOL=0 idle state. Consult your slave device datasheet for exact timing requirements.

```c
// Configure for SPI Mode 0 (most common)
uint32_t ctrl = SPI_CTRL;
ctrl &= ~((1 << 10) | (1 << 9));  // Clear Tx_NEG and Rx_NEG
ctrl |= (0 << 10) | (1 << 9);     // Tx_NEG=0, Rx_NEG=1
SPI_CTRL = ctrl;
```

### 3.4 Configuring Bit Order

Most SPI devices use MSB-first transmission. Configure the LSB bit accordingly:

```c
uint32_t ctrl = SPI_CTRL;

// MSB first (default, standard SPI)
ctrl &= ~(1 << 11);

// Or LSB first (if required by slave)
// ctrl |= (1 << 11);

SPI_CTRL = ctrl;
```

### 3.5 Configuring Slave Select Mode

Choose between automatic and manual slave select control:

**Automatic Mode (ASS=1):**
- Slave select asserts automatically when transfer starts
- Slave select deasserts automatically when transfer completes
- Recommended for simple single-transfer operations

**Manual Mode (ASS=0):**
- Software controls slave select assertion/deassertion
- Required for multi-transfer operations without deasserting SS
- Required for protocols that need SS held low across multiple transfers

```c
// Enable automatic slave select
SPI_CTRL |= (1 << 13);

// Or use manual slave select
// SPI_CTRL &= ~(1 << 13);
```

### 3.6 Complete Configuration Example

```c
void spi_configure(uint16_t divider, uint8_t char_len, 
                   uint8_t tx_neg, uint8_t rx_neg,
                   uint8_t lsb_first, uint8_t auto_ss) {
    // Set clock divider
    SPI_DIVIDER = divider;
    
    // Build CTRL register value
    uint32_t ctrl = 0;
    ctrl |= (char_len & 0x7F);           // CHAR_LEN
    ctrl |= (rx_neg ? (1 << 9) : 0);     // Rx_NEG
    ctrl |= (tx_neg ? (1 << 10) : 0);    // Tx_NEG
    ctrl |= (lsb_first ? (1 << 11) : 0); // LSB
    ctrl |= (auto_ss ? (1 << 13) : 0);   // ASS
    
    SPI_CTRL = ctrl;
}

// Example: 8-bit, SPI Mode 0, MSB first, automatic SS, 1 MHz clock
spi_configure(49, 8, 0, 1, 0, 1);
```

---

## 4. Performing Data Transfers

### 4.1 Basic Transfer with Automatic Slave Select

This is the simplest transfer method, suitable for single transfers to a slave device:

```c
uint32_t spi_transfer_auto_ss(uint32_t tx_data, uint8_t slave) {
    // 1. Select the target slave
    SPI_SS = (1 << slave);
    
    // 2. Write transmit data
    SPI_TX0 = tx_data;
    
    // 3. Start transfer (read current CTRL, set GO_BSY)
    uint32_t ctrl = SPI_CTRL;
    ctrl |= (1 << 8);  // Set GO_BSY
    SPI_CTRL = ctrl;
    
    // 4. Wait for transfer to complete
    while (SPI_CTRL & (1 << 8)) {
        // Optionally yield to OS or do other work
    }
    
    // 5. Read received data
    return SPI_RX0;
}
```

### 4.2 Basic Transfer with Manual Slave Select

Use manual control when you need to perform multiple transfers with slave select held low:

```c
void spi_select_slave(uint8_t slave) {
    SPI_SS = (1 << slave);
}

void spi_deselect_slave(void) {
    SPI_SS = 0;
}

uint32_t spi_transfer(uint32_t tx_data) {
    // Write transmit data
    SPI_TX0 = tx_data;
    
    // Start transfer
    uint32_t ctrl = SPI_CTRL;
    ctrl |= (1 << 8);
    SPI_CTRL = ctrl;
    
    // Wait for completion
    while (SPI_CTRL & (1 << 8));
    
    // Return received data
    return SPI_RX0;
}

// Example: Read 3 bytes from slave with SS held low
void read_multiple_bytes(uint8_t slave, uint8_t *buffer) {
    spi_select_slave(slave);
    
    buffer[0] = spi_transfer(0xFF);  // Send dummy, receive data
    buffer[1] = spi_transfer(0xFF);
    buffer[2] = spi_transfer(0xFF);
    
    spi_deselect_slave();
}
```

### 4.3 Multi-Word Transfers (>32 bits)

For transfers larger than 32 bits, use multiple data registers:

```c
// 64-bit transfer
void spi_transfer_64(uint32_t tx_high, uint32_t tx_low,
                     uint32_t *rx_high, uint32_t *rx_low) {
    // Configure for 64-bit transfer
    uint32_t ctrl = SPI_CTRL;
    ctrl = (ctrl & ~0x7F) | 64;  // CHAR_LEN = 64
    SPI_CTRL = ctrl;
    
    // Load transmit data
    SPI_TX0 = tx_low;   // Bits 31:0
    SPI_TX1 = tx_high;  // Bits 63:32
    
    // Start transfer
    SPI_CTRL = ctrl | (1 << 8);
    
    // Wait for completion
    while (SPI_CTRL & (1 << 8));
    
    // Read received data
    *rx_low = SPI_RX0;
    *rx_high = SPI_RX1;
}
```

### 4.4 Interrupt-Driven Transfers

For better CPU efficiency, use interrupt-driven transfers:

```c
volatile int transfer_complete = 0;
volatile uint32_t received_data = 0;

void spi_isr(void) {
    // Read data (also clears interrupt)
    received_data = SPI_RX0;
    transfer_complete = 1;
}

void spi_transfer_async(uint32_t tx_data, uint8_t slave) {
    transfer_complete = 0;
    
    // Select slave
    SPI_SS = (1 << slave);
    
    // Write transmit data
    SPI_TX0 = tx_data;
    
    // Enable interrupt and start transfer
    uint32_t ctrl = SPI_CTRL;
    ctrl |= (1 << 12);  // IE = 1
    ctrl |= (1 << 8);   // GO_BSY = 1
    SPI_CTRL = ctrl;
}

// In main code
void example_async_transfer(void) {
    spi_transfer_async(0xA5, 0);
    
    // Do other work while transfer is in progress
    // ...
    
    // Wait for completion if needed
    while (!transfer_complete);
    
    // Use received_data
    process_data(received_data);
}
```

---

## 5. Common Operations

### 5.1 Reading a Device Register

Many SPI devices follow a command/response protocol. To read a register:

```c
uint8_t spi_read_register(uint8_t slave, uint8_t reg_addr) {
    // Configure for 16-bit transfer (8-bit address + 8-bit data)
    uint32_t ctrl = SPI_CTRL;
    ctrl = (ctrl & ~0x7F) | 16;
    SPI_CTRL = ctrl;
    
    spi_select_slave(slave);
    
    // Send read command (typically address with MSB=0 or specific read bit)
    // and dummy byte, receive data in lower byte
    SPI_TX0 = (reg_addr << 8) | 0x00;
    
    SPI_CTRL = ctrl | (1 << 8);
    while (SPI_CTRL & (1 << 8));
    
    uint32_t rx = SPI_RX0;
    
    spi_deselect_slave();
    
    return rx & 0xFF;
}
```

### 5.2 Writing a Device Register

```c
void spi_write_register(uint8_t slave, uint8_t reg_addr, uint8_t value) {
    // Configure for 16-bit transfer
    uint32_t ctrl = SPI_CTRL;
    ctrl = (ctrl & ~0x7F) | 16;
    SPI_CTRL = ctrl;
    
    spi_select_slave(slave);
    
    // Send write command (typically address with MSB=1 or specific write bit)
    SPI_TX0 = ((reg_addr | 0x80) << 8) | value;
    
    SPI_CTRL = ctrl | (1 << 8);
    while (SPI_CTRL & (1 << 8));
    
    spi_deselect_slave();
}
```

### 5.3 Burst Read/Write Operations

For reading or writing multiple consecutive bytes:

```c
void spi_burst_read(uint8_t slave, uint8_t start_addr, 
                    uint8_t *buffer, size_t len) {
    // Configure for 8-bit transfers
    uint32_t ctrl = SPI_CTRL & ~0x7F;
    ctrl |= 8;
    ctrl &= ~(1 << 13);  // Manual SS
    SPI_CTRL = ctrl;
    
    spi_select_slave(slave);
    
    // Send start address (with read bit if required by device)
    SPI_TX0 = start_addr;
    SPI_CTRL = ctrl | (1 << 8);
    while (SPI_CTRL & (1 << 8));
    
    // Read data bytes
    for (size_t i = 0; i < len; i++) {
        SPI_TX0 = 0xFF;  // Dummy byte
        SPI_CTRL = ctrl | (1 << 8);
        while (SPI_CTRL & (1 << 8));
        buffer[i] = SPI_RX0 & 0xFF;
    }
    
    spi_deselect_slave();
}
```

---

## 6. Initialization Sequence

The recommended initialization sequence for the SPI core:

```c
void spi_init(void) {
    // 1. Wait for any pending transfer to complete
    while (SPI_CTRL & (1 << 8));
    
    // 2. Configure clock divider (example: 1 MHz with 100 MHz system clock)
    SPI_DIVIDER = 49;
    
    // 3. Deselect all slaves
    SPI_SS = 0;
    
    // 4. Configure CTRL register
    //    - CHAR_LEN = 8 (8-bit transfers)
    //    - Rx_NEG = 1, Tx_NEG = 0 (SPI Mode 0)
    //    - LSB = 0 (MSB first)
    //    - IE = 0 (interrupts disabled initially)
    //    - ASS = 1 (automatic slave select)
    uint32_t ctrl = 0;
    ctrl |= 8;           // CHAR_LEN = 8
    ctrl |= (1 << 9);    // Rx_NEG = 1
    ctrl |= (1 << 13);   // ASS = 1
    SPI_CTRL = ctrl;
    
    // 5. Clear any pending interrupt by reading a register
    volatile uint32_t dummy = SPI_CTRL;
    (void)dummy;
}
```

---

## 7. Troubleshooting

### 7.1 No Clock Output

**Symptoms:** `sclk_pad_o` remains idle, no data transfer occurs.

**Possible Causes:**
1. GO_BSY bit not set
2. Transfer already in progress (GO_BSY ignored)
3. DIVIDER set to maximum value (very slow clock)

**Solutions:**
- Verify GO_BSY is written as 1
- Wait for previous transfer to complete before starting new one
- Check DIVIDER register value

### 7.2 Incorrect Data Received

**Symptoms:** Data received does not match expected values.

**Possible Causes:**
1. Incorrect SPI mode (Tx_NEG/Rx_NEG mismatch)
2. Wrong bit order (LSB vs MSB)
3. Incorrect character length
4. Clock frequency too high for slave device

**Solutions:**
- Verify Tx_NEG and Rx_NEG settings match slave requirements
- Check LSB bit setting
- Verify CHAR_LEN matches expected transfer size
- Reduce clock frequency by increasing DIVIDER

### 7.3 Slave Not Responding

**Symptoms:** Slave select asserts but no response from slave.

**Possible Causes:**
1. Wrong slave select bit set
2. Slave select active level incorrect (should be active low)
3. ASS mode confusion

**Solutions:**
- Verify correct SS register bit is set
- Check slave device wiring
- Confirm ASS setting matches intended control method

### 7.4 Transfer Hangs

**Symptoms:** GO_BSY never clears, transfer appears stuck.

**Possible Causes:**
1. CHAR_LEN set to 0 (128-bit transfer takes longer)
2. DIVIDER set to very high value (slow clock)
3. Hardware issue

**Solutions:**
- Check CHAR_LEN is set to expected value
- Verify DIVIDER produces reasonable clock frequency
- Check system reset and clock signals

---

## 8. Quick Reference

### Register Summary

| Register | Offset | Key Fields |
|----------|--------|------------|
| Tx0/Rx0  | 0x00   | Data bits 31:0 |
| Tx1/Rx1  | 0x04   | Data bits 63:32 |
| Tx2/Rx2  | 0x08   | Data bits 95:64 |
| Tx3/Rx3  | 0x0C   | Data bits 127:96 |
| CTRL     | 0x10   | ASS, IE, LSB, Tx_NEG, Rx_NEG, GO_BSY, CHAR_LEN |
| DIVIDER  | 0x14   | DIVIDER[15:0] |
| SS       | 0x18   | SS[7:0] |

### CTRL Register Quick Reference

| Bit | Name     | Description |
|-----|----------|-------------|
| 13  | ASS      | 1=auto SS, 0=manual SS |
| 12  | IE       | 1=interrupt enabled |
| 11  | LSB      | 1=LSB first, 0=MSB first |
| 10  | Tx_NEG   | 1=MOSI changes on falling edge |
| 9   | Rx_NEG   | 1=MISO sampled on falling edge |
| 8   | GO_BSY   | Write 1 to start, read for status |
| 6:0 | CHAR_LEN | Bits per transfer (1-127, 0=128) |

### Common SPI Mode Settings

| Mode | Tx_NEG | Rx_NEG |
|------|--------|--------|
| 0    | 0      | 1      |
| 1    | 1      | 0      |
| 2    | 1      | 0      |
| 3    | 0      | 1      |

---

## Appendix A: Software Interface Structures

For embedded systems using structured register access, the following definitions can be used:

```c
// CTRL register structure
typedef struct {
    uint32_t char_len  : 7;   // Bits 6:0
    uint32_t reserved0 : 1;   // Bit 7
    uint32_t go_bsy    : 1;   // Bit 8
    uint32_t rx_neg    : 1;   // Bit 9
    uint32_t tx_neg    : 1;   // Bit 10
    uint32_t lsb       : 1;   // Bit 11
    uint32_t ie        : 1;   // Bit 12
    uint32_t ass       : 1;   // Bit 13
    uint32_t reserved1 : 18;  // Bits 31:14
} spi_ctrl_t;

// Register file structure
typedef struct {
    volatile uint32_t data[4];  // 0x00-0x0C: Tx/Rx registers
    volatile uint32_t ctrl;     // 0x10: Control register
    volatile uint32_t divider;  // 0x14: Clock divider
    volatile uint32_t ss;       // 0x18: Slave select
} spi_regs_t;

// Base address (system dependent)
#define SPI_BASE ((spi_regs_t *)0x40000000)
```

---

*Document Revision: 1.0*  
*Based on OpenCores SPI Master Core Specification Rev 0.6*
