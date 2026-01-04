# SPI Master Core Operations

## Overview

The SPI Master Core is a WISHBONE-compliant synchronous serial controller that supports full-duplex data transfers with variable word lengths up to 128 bits. This document summarizes the key operations that can be performed with the IP.

---

## 1. Data Transfer Operations

### 1.1 Transmit Data
**Purpose:** Load data into transmit registers for the next SPI transfer.

**Registers:** Tx0 (0x00), Tx1 (0x04), Tx2 (0x08), Tx3 (0x0c)

**Description:**
- Write data to TxX registers before initiating a transfer
- The number of registers used depends on CHAR_LEN:
  - ≤32 bits: Use Tx0 only
  - ≤64 bits: Use Tx0, Tx1
  - ≤96 bits: Use Tx0, Tx1, Tx2
  - ≤128 bits: Use Tx0, Tx1, Tx2, Tx3

### 1.2 Receive Data
**Purpose:** Read data received from the last SPI transfer.

**Registers:** Rx0 (0x00), Rx1 (0x04), Rx2 (0x08), Rx3 (0x0c)

**Description:**
- Read RxX registers after transfer completion
- Valid bits depend on CHAR_LEN configuration
- RxX and TxX registers share the same flip-flops (read-only access for Rx)

### 1.3 Start Transfer
**Purpose:** Initiate an SPI data transfer.

**Register:** CTRL (0x10), bit 8 (GO_BSY)

**Description:**
- Write 1 to GO_BSY bit to start the transfer
- All other registers must be configured before setting GO_BSY
- Writing 0 to GO_BSY has no effect
- Register writes during an active transfer are ignored

### 1.4 Poll Transfer Status
**Purpose:** Check if a transfer is in progress or completed.

**Register:** CTRL (0x10), bit 8 (GO_BSY)

**Description:**
- Read GO_BSY bit: 1 = transfer in progress, 0 = transfer complete
- GO_BSY is automatically cleared when transfer finishes

---

## 2. Configuration Operations

### 2.1 Set Character Length
**Purpose:** Configure the number of bits per transfer.

**Register:** CTRL (0x10), bits 6:0 (CHAR_LEN)

**Description:**
- CHAR_LEN = 0x01: 1 bit
- CHAR_LEN = 0x02: 2 bits
- ...
- CHAR_LEN = 0x7F: 127 bits
- CHAR_LEN = 0x00: 128 bits

### 2.2 Set Clock Divider
**Purpose:** Configure the SPI serial clock frequency.

**Register:** DIVIDER (0x14), bits 15:0

**Description:**
- Serial clock frequency: f_sclk = f_wb_clk / ((DIVIDER + 1) * 2)
- Default value: 0xFFFF
- Lower values produce higher SPI clock frequencies

### 2.3 Set Bit Order
**Purpose:** Configure MSB-first or LSB-first transmission.

**Register:** CTRL (0x10), bit 11 (LSB)

**Description:**
- LSB = 0: MSB transmitted/received first (SPI/Microwire compliant)
- LSB = 1: LSB transmitted/received first

### 2.4 Set Clock Edge Timing
**Purpose:** Configure which clock edge is used for data transitions.

**Register:** CTRL (0x10), bits 10 (Tx_NEG) and 9 (Rx_NEG)

**Description:**
- **Tx_NEG:**
  - 0: MOSI changes on rising edge of SCLK
  - 1: MOSI changes on falling edge of SCLK
- **Rx_NEG:**
  - 0: MISO latched on rising edge of SCLK
  - 1: MISO latched on falling edge of SCLK

---

## 3. Slave Select Operations

### 3.1 Manual Slave Select
**Purpose:** Directly control slave select lines via software.

**Registers:** SS (0x18), CTRL bit 13 (ASS)

**Description:**
- Set ASS = 0 for manual control
- Write 1 to SS register bits to assert corresponding ss_pad_o lines
- Write 0 to deassert the lines
- Supports up to 8 slave select lines (bits 7:0)

### 3.2 Automatic Slave Select
**Purpose:** Automatically assert/deassert slave select during transfers.

**Registers:** SS (0x18), CTRL bit 13 (ASS)

**Description:**
- Set ASS = 1 for automatic control
- Write 1 to desired SS register bits to select target slave(s)
- ss_pad_o is automatically asserted when GO_BSY is set
- ss_pad_o is automatically deasserted when transfer completes

### 3.3 Select Slave Device
**Purpose:** Choose which slave device(s) to communicate with.

**Register:** SS (0x18), bits 7:0

**Description:**
- Each bit corresponds to one slave select line (ss_pad_o[7:0])
- Multiple slaves can be selected simultaneously
- Active-low output signals

---

## 4. Interrupt Operations

### 4.1 Enable Interrupt
**Purpose:** Configure interrupt generation on transfer completion.

**Register:** CTRL (0x10), bit 12 (IE)

**Description:**
- Set IE = 1 to enable interrupt output (wb_int_o)
- Interrupt asserts when transfer completes

### 4.2 Clear Interrupt
**Purpose:** Deassert the interrupt signal.

**Description:**
- Perform any read or write access to any SPI register
- This automatically clears the interrupt

---

## 5. Typical Operation Sequences

### 5.1 Basic SPI Transfer (8-bit, Manual SS)

1. **Configure clock divider:** Write DIVIDER register
2. **Configure transfer parameters:** Write CTRL with CHAR_LEN=8, desired Tx_NEG/Rx_NEG, LSB=0, ASS=0
3. **Load transmit data:** Write Tx0 register
4. **Assert slave select:** Write SS register (e.g., 0x01 for slave 0)
5. **Start transfer:** Write CTRL with GO_BSY=1
6. **Wait for completion:** Poll GO_BSY until cleared (or use interrupt)
7. **Read received data:** Read Rx0 register
8. **Deassert slave select:** Write SS register with 0x00

### 5.2 Basic SPI Transfer (8-bit, Automatic SS)

1. **Configure clock divider:** Write DIVIDER register
2. **Select slave:** Write SS register (e.g., 0x01 for slave 0)
3. **Configure transfer:** Write CTRL with CHAR_LEN=8, ASS=1, other settings
4. **Load transmit data:** Write Tx0 register
5. **Start transfer:** Write CTRL with GO_BSY=1
6. **Wait for completion:** Poll GO_BSY until cleared
7. **Read received data:** Read Rx0 register

### 5.3 Multi-Byte Transfer (32-bit)

1. **Configure:** Set CHAR_LEN=32 in CTRL register
2. **Load data:** Write 32-bit value to Tx0
3. **Start and wait:** Set GO_BSY, poll until complete
4. **Read result:** Read 32-bit value from Rx0

---

## Register Quick Reference

| Register | Address | Access | Description |
|----------|---------|--------|-------------|
| Rx0-Rx3  | 0x00-0x0C | R | Receive data registers |
| Tx0-Tx3  | 0x00-0x0C | R/W | Transmit data registers |
| CTRL     | 0x10 | R/W | Control and status register |
| DIVIDER  | 0x14 | R/W | Clock divider register |
| SS       | 0x18 | R/W | Slave select register |

## CTRL Register Bit Map

| Bit(s) | Name | Description |
|--------|------|-------------|
| 13 | ASS | Automatic slave select enable |
| 12 | IE | Interrupt enable |
| 11 | LSB | LSB-first transmission |
| 10 | Tx_NEG | MOSI change on falling edge |
| 9 | Rx_NEG | MISO latch on falling edge |
| 8 | GO_BSY | Start transfer / busy status |
| 6:0 | CHAR_LEN | Character length (1-128 bits) |
