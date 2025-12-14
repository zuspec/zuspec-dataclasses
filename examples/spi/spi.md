SPI Master Core

Specification

Author: Simon Srot
simons@opencores.org

Rev. 0.6
March 15, 2004

OpenCores

SPI Master Core Specification

3/15/2004

Revision History

Description

Author
Simon Srot  First Draft
Simon Srot  Document is lectured.
Simon Srot  Support for 64 bit character len added.

Simon Srot  Automatic slave select signal generation added.

Simon Srot  Support for 128 bit character len added.
Simon Srot  Bit fields in CTRL changed.

Rev.  Date
0.1
0.2
0.3

June 13, 2002
July 12, 2002
December  28,
2002
March
2003
April 15 2003
March
2004

26,

15,

0.4

0.5
0.6

www.opencores.org

Rev 0.5

i

OpenCores

SPI Master Core Specification

3/15/2004

Contents

CONTENTS.......................................................................................................... II

INTRODUCTION................................................................................................. 1

IO PORTS.............................................................................................................. 2

2.1 WISHBONE INTERFACE SIGNALS.................................................................. 2
2.2 SPI EXTERNAL CONNECTIONS......................................................................... 2

REGISTERS .......................................................................................................... 3

3.1 CORE REGISTERS LIST .................................................................................... 3
3.2 DATA RECEIVE REGISTER LOW/HIGH[RXL/RXH]............................................ 3
3.3 DATA TRANSMIT REGISTER LOW/HIGH[TXL/TXH] ......................................... 4
3.4 CONTROL AND STATUS REGISTER [CTRL]...................................................... 4
3.5 DIVIDER REGISTER [DIVIDER]...................................................................... 5
3.6 SLAVE SELECT REGISTER [SS] ........................................................................ 5

OPERATION......................................................................................................... 7

4.1 WISHBONE INTERFACE................................................................................ 7
4.2 SERIAL INTERFACE ......................................................................................... 7

ARCHITECTURE ................................................................................................ 9

CORE CONFIGURATION ............................................................................... 10

www.opencores.org

Rev 0.5

ii

OpenCores

SPI Master Core Specification

3/15/2004

Introduction

This document provides specifications for the SPI (Serial Peripheral Interface) Master
core. Synchronous serial interfaces are widely used to provide economical board-level
interfaces  between  different  devices  such  as  microcontrollers,  DACs,  ADCs  and
other.  Although  there  is  no  single  standard  for  a  synchronous  serial  bus,  there  are
industry-wide accepted guidelines based on two most popular implementations:

SPI (a trademark of Motorola Semiconductor)
Microwire/Plus (a trademark of National Semiconductor)

Many  IC  manufacturers  produce  components  that  are  compatible  with  SPI  and
Microwire/Plus.
The  SPI  Master  core  is  compatible  with  both  above-mentioned  protocols  as  master
with some additional functionality. At the hosts side, the core acts like a WISHBONE
compliant slave device.

Features:

Full duplex synchronous serial data transfer
Variable length of transfer word up to 128 bits
MSB or LSB first data transfer
Rx and Tx on both rising or falling edge of serial clock independently
8 slave select lines
Fully static synchronous design with one clock domain
Technology independent Verilog
Fully synthesizable

www.opencores.org

Rev 0.6

1 of 10

OpenCores

SPI Master Core Specification

3/15/2004

2.1 WISHBONE interface signals

IO ports

Port
wb_clk_i
wb_rst_i
wb_adr_i
wb_dat_i
wb_dat_o
wb_sel_i
wb_we_i
wb_stb_i
wb_cyc_i
wb_ack_o
wb_err_o
wb_int_o

Width  Direction  Description
Master clock
Synchronous reset, active high
Lower address bits
Data towards the core
Data from the core
Byte select signals
Write enable input
Strobe signal/Core select input
Valid bus cycle input
Bus cycle acknowledge output
Bus cycle error output
Interrupt signal output

Input
Input
Input
Input
Output
Input
Input
Input
Input
Output
Output
Output

1
1
5
32
32
4
1
1
1
1
1
1

Table 1: Wishbone interface signals

All  output  WISHBONE  signals  are  registered  and  driven  on  the  rising  edge  of
wb_clk_i. All input WISHBONE signals are latched on the rising edge of wb_clk_i.

2.2 SPI external connections

Port
/ss_pad_o
sclk_pad_o
mosi_pad_o
miso_pad_i

Width  Direction  Description

8
1
1
1

Output
Output
Output
Input

Slave select output signals
Serial clock output
Master out slave in data signal output
Master in slave out data signal input

Table 2: SPI  external connections

www.opencores.org

Rev 0.6

2 of 10

OpenCores

SPI Master Core Specification

3/15/2004

Registers

3.1 Core Registers list

Name
Rx0
Rx1
Rx2
Rx3
Tx0
Tx1
Tx2
Tx3
CTRL
DIVIDER
SS

Address  Width

0x00
0x04
0x08
0x0c
0x00
0x04
0x08
0x0c
0x10
0x14
0x18

32
32
32
32
32
32
32
32
32
32
32

Access
R
R
R
R
R/W
R/W
R/W
R/W
R/W
R/W
R/W

Description
Data receive register 0
Data receive register 1
Data receive register 2
Data receive register 3
Data transmit register 0
Data transmit register 1
Data transmit register 2
Data transmit register 3
Control and status register
Clock divider register
Slave select register

Table 3: List of core registers

All  registers  are  32-bit  wide  and  accessible  only  with  32  bits  (all  wb_sel_i  signals
must be active).

3.2 Data receive registers[RxX]

Bit #
Access
Name

31:0
R
Rx

Reset Value: 0x00000000

Table 4: Data Receive register

RxX
The  Data  Receive  registers  hold  the  value  of  received  data  of  the  last  executed
transfer. Valid bits depend on the character  length field  in  the CTRL register (i.e.  if
CTRL[9:3] is set to 0x08, bit RxL[7:0] holds the received data).  If character length is
less or equal to 32 bits, Rx1,Rx2 and Rx3 are not used, if character length is less than
64 bits, Rx2 and Rx3 are not used and so on.

NOTE: The Data Received registers are read-only registers. A Write to these registers
will  actually  modify  the  Transmit  registers  because  those  registers  share  the  same
FFs.

www.opencores.org

Rev 0.6

3 of 10

OpenCores

SPI Master Core Specification

3/15/2004

3.3 Data transmit register [TxX]

Bit #
Access
Name

31:0
R/W
Tx

Reset Value: 0x00000000

Table 5: Data Transmit register

TxX
The Data Receive registers hold the data to be transmitted in the next transfer. Valid
bits depend on the character length field in the CTRL register (i.e. if CTRL[9:3] is set
to  0x08,  the  bit  Tx0[7:0]  will  be  transmitted  in  next  transfer).  If  character  length  is
less or equal to 32 bits, Tx1, Tx2 and Tx3 are not used, if character len is less than 64
bits, Tx2 and Tx3 are not used and so on.

3.4 Control and status register [CTRL]

Bit #
Access
Name  Reserved  ASS

13
11
12
R/W  R/W  R/W
LSB
IE

31:14
R

10
R/W

9
R/W

8
R/W

7
R

6:0
R/W

Tx_NEG  Rx_NEG  GO_BSY  Reserved  CHAR_LEN

Reset Value: 0x00000000

Table 6: Control and Status register

ASS
If this bit is set, ss_pad_o signals are generated automatically. This means that slave
select signal, which is selected in SS register is asserted by the SPI controller, when
transfer  is  started  by  setting  CTRL[GO_BSY]  and  is  de-asserted  after  transfer  is
finished.  If  this  bit  is  cleared,  slave  select  signals  are  asserted  and  de-aserted  by
writing and clearing bits in SS register.

IE
If  this  bit  is  set,  the  interrupt  output  is  set  active  after  a  transfer  is  finished.  The
Interrupt signal is deasserted after a Read or Write to any register.

LSB
If this bit is set, the LSB is sent first on the line (bit TxL[0]), and the first bit received
from the line will be put in the LSB position in the Rx register (bit RxL[0]). If this bit
is cleared, the MSB is transmitted/received first (which bit in TxX/RxX register that is
depends on the CHAR_LEN field in the CTRL register).

Tx_NEG
If this bit is set, the mosi_pad_o signal is changed on the falling edge of a sclk_pad_o
clock  signal,  or  otherwise  the  mosi_pad_o  signal  is  changed  on  the  rising  edge  of
sclk_pad_o.

www.opencores.org

Rev 0.6

4 of 10

OpenCores

SPI Master Core Specification

3/15/2004

Rx_NEG
If this bit is set, the miso_pad_i signal is latched on the falling edge of a sclk_pad_o
clock  signal,  or  otherwise  the  miso_pad_i  signal  is  latched  on  the  rising  edge  of
sclk_pad_o.

GO_BSY
Writing 1 to this bit starts the transfer. This bit remains set during the transfer and is
automatically cleared after the transfer finished. Writing 0 to this bit has no effect.

NOTE:  All  registers,  including  the  CTRL  register,  should  be  set  before  writing  1  to
the GO_BSY bit in the CTRL register. The configuration in the CTRL register must be
changed with the GO_BSY bit cleared,   i.e. two Writes to the CTRL register must be
executed  when  changing  the  configuration  and  performing  the  next  transfer,  firstly
with the GO_BSY bit cleared and secondly with GO_BSY bit set to start the transfer.
When a transfer is in progress, writing to any register of the SPI Master core has no
effect.

CHAR_LEN
This field specifies how many bits are transmitted in one transfer. Up to 64 bits can be
transmitted.
CHAR_LEN = 0x01 … 1 bit
CHAR_LEN = 0x02 … 2 bits
…
CHAR_LEN = 0x7f … 127 bits
CHAR_LEN = 0x00 … 128 bits

3.5 Divider register [DIVIDER]

Bit #
Access
Name

31:16
R
Reserved

15:0
R/W
DIVIDER

Reset Value: 0x0000ffff

Table 7: Divider register

DIVIDER
The  value  in  this  field  is  the  frequency  divider  of  the  system  clock  wb_clk_i  to
generate the serial clock on the output sclk_pad_o. The desired frequency is obtained
according to the following equation:

f

sclk

f

wb

clk
_
DIVIDER

21

3.6 Slave select register [SS]

Bit #
Access

31:8
R

7:0
R/W

www.opencores.org

Rev 0.6

5 of 10

OpenCores

SPI Master Core Specification

3/15/2004

Name

Reserved

SS

Reset Value: 0x00000000

Table 8: Slave Select register

SS
If CTRL[ASS] bit is cleared, writing 1 to any bit location of this field sets the proper
ss_pad_o  line  to  an  active  state  and  writing  0  sets  the  line  back  to  inactive  state.  If
CTRL[ASS] bit is set, writing 1 to any bit location of this field will select appropriate
ss_pad_o line to be automatically driven to active state for the duration of the transfer,
and will be driven to inactive state for the rest of the time.

www.opencores.org

Rev 0.6

6 of 10

OpenCores

SPI Master Core Specification

3/15/2004

Operation

This  core  is  an  SPI  and  Microwire/Plus  compliant  synchronous  serial  controller.  At
the host side, it is controlled via registers accessible through a WISHBONE rev. B1
interface.

E
N
O
B
H
S
I
W

E
N
O
B
H
S
W

I

/ss_pad_o[0]
/ss_pad_o[1]
/ss_pad_o[2]

/ss_pad_o[0]
/ss_pad_o[1]
/ss_pad_o[2]
MASTER

sclk_pad_o

MASTER

sclk_pad_o

mosi_pad_o
miso_pad_i

mosi_pad_o
miso_pad_i

MISO  MOSI  SCLK  /SS

MISO  MOSI  SCLK / SS

MISO  MOSI  SCLK  /SS

MISO MOSI SCLK/SS
SLAVE 0

SLAVE 0

MISO MOSI SCLK/SS
SLAVE 1

SLAVE 1

MISO MOSI SCLK/SS
SLAVE 2

SLAVE 2

4.1 WISHBONE interface

The  SPI  core  has  five  32-bit  registers  through  the  WISHBONE  rev.  B1  compatible
interface. All accesses to SPI registers must be 32-bit (wb_sel[3:0] = 0xf). Please refer
to the WISHBONE specification at
http://www.opencores.org/wishbone/specs/wbspec_b1.pdf

4.2 Serial interface

The  serial  interface  consists  of  slave  select  lines,  serial  clock  lines,  as  well  as  input
and  output  data  lines.  All  transfers  are  full  duplex  transfers  of  a  programmable
number of bits per transfer (up to 64 bits).
Compared to the SPI/Microwire protocol, this core has some additional functionality.
It  can  drive  data  to  the  output  data  line  in  respect  to  the  falling  (SPI/Microwire
compliant) or rising edge of the serial clock, and it can latch data on an input data line
on the rising (SPI/Microwire compliant) or falling edge of a serial clock line. It also
can transmit (receive) the MSB first (SPI/Microwire compliant) or the LSB first.
It  is  important  to  know  that  the  RxX  and  TxX  registers  share  the  same  flip-flops,
which  means  that  what  is  received  from  the  input  data  line  in  one  transfer  will  be
transmitted on the output data line in the next transfer if no write access to the TxX
register is executed between the transfers.

www.opencores.org

Rev 0.6

7 of 10

OpenCores

SPI Master Core Specification

3/15/2004

ss_pad_o

sclk_pad_o

mosi_pad_o

miso_pad_i

MSB
(Tx[7])

MSB
(Rx[7])

LSB
(Tx[0])

LSB
(Rx[0])

CTRL[LSB] = 0, CTRL[CHAR_LEN] = 0x08, CTRL[TX_NEG] = 1, CTRL[RX_NEG] =  0

ss_pad_o

sclk_pad_o

mosi_pad_o

miso_pad_i

LSB
(Tx[0])

LSB
(Rx[0])

MSB
(Tx[9])

MSB
(Rx[9])

CTRL[LSB] = 1, CTRL[CHAR_LEN] = 0x0a, CTRL[TX_NEG] = 0, CTRL[RX_NEG] =  1

www.opencores.org

Rev 0.6

8 of 10

OpenCores

SPI Master Core Specification

3/15/2004

Architecture

The SPI Master core consists of three parts shown in the following figure:

s
u
B
C
O
S
E
N
O
B
H
S
I
H
W

e
c
a
f
r
e
t
n
I
E
N
O
B
H
S
I
H
W

Clock generator

spi_clgen.v

e
c
a
f
r
e
t
n
I

l
a
i
r
e
S

v
.
t
f
i
h
s
_
i
p
s

sclk_pad_o

ss_pad_o

mosi_pad_o

miso_pad_i

spi_top.v

www.opencores.org

Rev 0.6

9 of 10

OpenCores

SPI Master Core Specification

3/15/2004

Core configuration

To  meet  specific  system  requirements  and  size  constraints  on  behalf  of  the  core
functionality, the SPI Master core can be configuredby setting the appropriate define
directives in the spi_defines.v source file. The directives are as follows:

SPI_DIVIDER_BIT_NB
This parameter defines the maximum number of bits needed for the divider. Set this
parameter  accordingly  to  the  maximum  system  frequency  and  lowest  serial  clock
frequency:

SPI_DIVIDE

R_BIT_NB

log
2

Default value is 16.

f
sys

max

f

sclk

min

2

1

SPI_MAX_CHAR
This parameter defines the maximum number of bits that can be received/transmitted
in one transfer.
The default value is 64.

SPI_SS_NB
This parameter defines the number of slave select lines.
The default value is 8.

www.opencores.org

Rev 0.6

10 of 10


