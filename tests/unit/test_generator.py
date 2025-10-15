
from __future__ import annotations
import zuspec.dataclasses as zdc
from typing import Dict, List, Tuple

def test_gen():

    @zdc.dataclass
    class WishboneInitiator(zdc.Bundle):
        cyc : zdc.Bit = zdc.output()
        ack : zdc.Bit = zdc.input()

    @zdc.dataclass
    class WishboneTarget(zdc.Bundle):
        cyc : zdc.Bit = zdc.input()
        ack : zdc.Bit = zdc.output()

#     def do_crc(crcIn, data) -> int:
#         crc = 0
#         # (2, 8), (2)
#         # (0, 3, 9), (0, 3)
#         # (1, 2, 5, 11, (10, 1, 4)
#         crc[0] = crcIn[2] ^ crcIn[8] ^ data[2]
#         crc[1] = crcIn[0] ^ crcIn[3] ^ crcIn[9] ^ data[0] ^ data[3]
#     crc[2] = crcIn[0] ^ crcIn[1] ^ crcIn[4] ^ crcIn[10] ^ data[0] ^ data[1] ^ data[4];
#     crc[3] = crcIn[1] ^ crcIn[2] ^ crcIn[5] ^ crcIn[11] ^ data[1] ^ data[2] ^ data[5];
#     crc[4] = crcIn[0] ^ crcIn[2] ^ crcIn[3] ^ crcIn[6] ^ crcIn[12] ^ data[0] ^ data[2] ^ data[3] ^ data[6];
#     crc[5] = crcIn[1] ^ crcIn[3] ^ crcIn[4] ^ crcIn[7] ^ crcIn[13] ^ data[1] ^ data[3] ^ data[4] ^ data[7];
#     crc[6] = crcIn[4] ^ crcIn[5] ^ crcIn[14] ^ data[4] ^ data[5];
#     crc[7] = crcIn[0] ^ crcIn[5] ^ crcIn[6] ^ crcIn[15] ^ data[0] ^ data[5] ^ data[6];
#     crc[8] = crcIn[1] ^ crcIn[6] ^ crcIn[7] ^ crcIn[16] ^ data[1] ^ data[6] ^ data[7];
#     crc[9] = crcIn[7] ^ crcIn[17] ^ data[7];
#     crc[10] = crcIn[2] ^ crcIn[18] ^ data[2];
#     crc[11] = crcIn[3] ^ crcIn[19] ^ data[3];
#     crc[12] = crcIn[0] ^ crcIn[4] ^ crcIn[20] ^ data[0] ^ data[4];
#     crc[13] = crcIn[0] ^ crcIn[1] ^ crcIn[5] ^ crcIn[21] ^ data[0] ^ data[1] ^ data[5];
#     crc[14] = crcIn[1] ^ crcIn[2] ^ crcIn[6] ^ crcIn[22] ^ data[1] ^ data[2] ^ data[6];
#     crc[15] = crcIn[2] ^ crcIn[3] ^ crcIn[7] ^ crcIn[23] ^ data[2] ^ data[3] ^ data[7];
#     crc[16] = crcIn[0] ^ crcIn[2] ^ crcIn[3] ^ crcIn[4] ^ crcIn[24] ^ data[0] ^ data[2] ^ data[3] ^ data[4];
#     crc[17] = crcIn[0] ^ crcIn[1] ^ crcIn[3] ^ crcIn[4] ^ crcIn[5] ^ crcIn[25] ^ data[0] ^ data[1] ^ data[3] ^ data[4] ^ data[5];
#     crc[18] = crcIn[0] ^ crcIn[1] ^ crcIn[2] ^ crcIn[4] ^ crcIn[5] ^ crcIn[6] ^ crcIn[26] ^ data[0] ^ data[1] ^ data[2] ^ data[4] ^ data[5] ^ data[6];
#     crc[19] = crcIn[1] ^ crcIn[2] ^ crcIn[3] ^ crcIn[5] ^ crcIn[6] ^ crcIn[7] ^ crcIn[27] ^ data[1] ^ data[2] ^ data[3] ^ data[5] ^ data[6] ^ data[7];
#     crc[20] = crcIn[3] ^ crcIn[4] ^ crcIn[6] ^ crcIn[7] ^ crcIn[28] ^ data[3] ^ data[4] ^ data[6] ^ data[7];
#     crc[21] = crcIn[2] ^ crcIn[4] ^ crcIn[5] ^ crcIn[7] ^ crcIn[29] ^ data[2] ^ data[4] ^ data[5] ^ data[7];
#     crc[22] = crcIn[2] ^ crcIn[3] ^ crcIn[5] ^ crcIn[6] ^ crcIn[30] ^ data[2] ^ data[3] ^ data[5] ^ data[6];
#     crc[23] = crcIn[3] ^ crcIn[4] ^ crcIn[6] ^ crcIn[7] ^ crcIn[31] ^ data[3] ^ data[4] ^ data[6] ^ data[7];
#     crc[24] = crcIn[0] ^ crcIn[2] ^ crcIn[4] ^ crcIn[5] ^ crcIn[7] ^ data[0] ^ data[2] ^ data[4] ^ data[5] ^ data[7];
#     crc[25] = crcIn[0] ^ crcIn[1] ^ crcIn[2] ^ crcIn[3] ^ crcIn[5] ^ crcIn[6] ^ data[0] ^ data[1] ^ data[2] ^ data[3] ^ data[5] ^ data[6];
#     crc[26] = crcIn[0] ^ crcIn[1] ^ crcIn[2] ^ crcIn[3] ^ crcIn[4] ^ crcIn[6] ^ crcIn[7] ^ data[0] ^ data[1] ^ data[2] ^ data[3] ^ data[4] ^ data[6] ^ data[7];
#     crc[27] = crcIn[1] ^ crcIn[3] ^ crcIn[4] ^ crcIn[5] ^ crcIn[7] ^ data[1] ^ data[3] ^ data[4] ^ data[5] ^ data[7];
#     crc[28] = crcIn[0] ^ crcIn[4] ^ crcIn[5] ^ crcIn[6] ^ data[0] ^ data[4] ^ data[5] ^ data[6];
#     crc[29] = crcIn[0] ^ crcIn[1] ^ crcIn[5] ^ crcIn[6] ^ crcIn[7] ^ data[0] ^ data[1] ^ data[5] ^ data[6] ^ data[7];
#     crc[30] = crcIn[0] ^ crcIn[1] ^ crcIn[6] ^ crcIn[7] ^ data[0] ^ data[1] ^ data[6] ^ data[7];
#     crc[31] = crcIn[1] ^ crcIn[7] ^ data[1] ^ data[7];
# end
# endfunction

    @zdc.dataclass
    class Interconnect(zdc.Component):
        targets : List[WishboneTarget] = zdc.field()
        initiators : List[WishboneInitiator] = zdc.field()

        # Note: binding is performed each time the netlist changes
        # This means it may be repeated many times
        # Elaborators should be able to avoid this and patch in
        # a new implementation
        @staticmethod
        def elaborate(c : Interconnect) -> Tuple[Interconnect, Dict]:
            """Expands generic data in the template class to produce
            a concrete class
            """

            # The type created by a generator must implement the interface
            # of its base type.
            # The generator has full control over the internals of the 
            # component. 

            # Have a 
            # Must be 

            return (None,None)


