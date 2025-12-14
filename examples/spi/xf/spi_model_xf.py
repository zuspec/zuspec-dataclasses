import zuspec.dataclasses as zdc
from typing import Tuple
from ..sw_if import SpiInitiatorOpIF

a : Tuple[int,int]
b : Tuple[zdc.uint8_t,zdc.uint8_t]
@zdc.dataclass
class SpiInitiatorXF(SpiInitiatorOpIF,zdc.Component):
    """Transfer-function model of the SPI controller"""
    sio : zdc.Transport[Tuple[zdc.uint8_t,zdc.uint128_t],zdc.uint128_t] = zdc.port()
    _char_len : zdc.uint8_t = zdc.field()
    _divider : zdc.uint16_t = zdc.field()
    _tgt_sel : zdc.uint8_t = zdc.field()
    clk_period : zdc.Time = zdc.field()

    async def configure(self, 
                        char_len : zdc.uint8_t,
                        divider : zdc.uint16_t,
                        tgt_sel : zdc.uint8_t):
        self._char_len = char_len
        self._divider = divider
        self._tgt_sel = tgt_sel

    async def tx(self, data : zdc.uint128_t, slave_select: int=0) -> zdc.uint128_t:
        # Transmit of each bit takes 2*(divider+1) clock periods
        await self.wait(self.clk_period * (2*self._divider+1) * self._char_len)
        ret = self.sio((self._tgt_sel, data))
        return ret

@zdc.dataclass
class SpiTargetXF(zdc.Component):
    sio : zdc.Transport[Tuple[zdc.uint8_t,zdc.uint128_t],zdc.uint128_t] = zdc.export()

    def __bind__(self): return {
        self.sio : self.rx
    }

    async def rx(self, tgt_sel : zdc.uint8_t, data : zdc.uint128_t) -> zdc.uint128_t:
        return 0
    