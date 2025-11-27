import zuspec.dataclasses as zdc
from typing import Protocol, List


@zdc.dataclass
class MemIF(Protocol):
    async def read(self, 
                   addr : int, 
                   size : int) -> bytearray: ...

    async def write(self, 
                    addr : int, 
                    data : bytearray, 
                    offset : int=0, 
                    size : int=-1): ...
    

@zdc.dataclass
class Dma(zdc.Component):
    m0 : MemIF = zdc.port()
    m1 : MemIF = zdc.port()

    _m0_lock : zdc.Resource = zdc.lock()
    _channel_busy : List[bool] = zdc.list(sz=16)

    # Capture the multiplicity of this function by tying it
    # to resource acquisition
    async def m2m(self,
                  channel : int,
                  src : int,
                  dst : int,
                  inc_src : bool,
                  inc_dst : bool,
                  xfer_sz : int,
                  xfer_tot : int,
                  xfer_chk : int=-1):
        # TODO: Check accidental concurrent use
        # This also allows us to see that local variables 
        # are associated with the channel, not the invocation
        assert self._channel_busy[channel] == False
        self._channel_busy[channel] = True

        if xfer_chk <= 0:
            xfer_chk = xfer_tot

        i = 0
        while i < xfer_tot:
            # Acquire access to the interface for a chunk
            # TODO: need to pass along priority data for the request
            await self._m0_lock.lock()
            j = 0
            while i < xfer_tot and j < xfer_chk:
                data = await self.m0.read(src, xfer_sz)
                await self.m0.write(dst, data, size=xfer_sz)
                i += 1
                j += 1

            self._m0_lock.release()
        pass
        self._channel_busy[channel] = False


    pass