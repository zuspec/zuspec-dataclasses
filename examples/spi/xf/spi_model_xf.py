import zuspec.dataclasses as zdc
from typing import Tuple
from ..sw_if import SpiInitiatorOpIF

a : Tuple[int,int]
b : Tuple[zdc.u8,zdc.u8]
@zdc.dataclass
class SpiInitiatorXF(SpiInitiatorOpIF,zdc.Component):
    """Transfer-function model of the SPI controller"""
    sio : zdc.Transport[Tuple[zdc.u8,zdc.u128],zdc.u128] = zdc.port()
    _char_len : zdc.u8 = zdc.field()
    _divider : zdc.u16 = zdc.field()
    _tgt_sel : zdc.u8 = zdc.field()
    clk_period : zdc.Time = zdc.field()

    async def configure(self, 
                        char_len : zdc.u8,
                        divider : zdc.u16,
                        tgt_sel : zdc.u8):
        self._char_len = char_len
        self._divider = divider
        self._tgt_sel = tgt_sel

    async def tx(self, data : zdc.u128, slave_select: int=0) -> zdc.u128:
        # Transmit of each bit takes 2*(divider+1) clock periods
        await self.wait(self.clk_period * (2*self._divider+1) * self._char_len)
        ret = self.sio((self._tgt_sel, data))
        return ret

@zdc.dataclass
class SpiTargetXF(zdc.Component):
    sio : zdc.Transport[Tuple[zdc.u8,zdc.u128],zdc.u128] = zdc.export()

    def __bind__(self): return {
        self.sio : self.rx
    }

    async def rx(self, tgt_sel : zdc.u8, data : zdc.u128) -> zdc.u128:
        return 0
    