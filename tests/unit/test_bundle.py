
from __future__ import annotations
import pytest
import zuspec.dataclasses as zdc
from typing import Dict, Optional, Self, Type

def test_smoke():


    @zdc.dataclass
    class WishboneInitiator(zdc.Bundle):
        ADR_WIDTH : int = zdc.const(default=32)
        DAT_WIDTH : int = zdc.const(default=32)
        adr : zdc.Bits = zdc.output(init=dict(width=lambda s:s.ADR_WIDTH))
        dat_w : zdc.Bits = zdc.output(init=dict(width=lambda s:s.DAT_WIDTH))
        dat_r : zdc.Bits = zdc.input(init=dict(width=lambda s:s.DAT_WIDTH))
        cyc : zdc.Bit = zdc.output()
        err : zdc.Bit = zdc.input()
        sel : zdc.Bits = zdc.output(init=dict(width=lambda s:int(s.DAT_WIDTH/8)))
        stb : zdc.Bit = zdc.output()
        ack : zdc.Bit = zdc.input()
        we : zdc.Bit = zdc.output()

        @staticmethod
        def idle(b : WishboneInitiator):
            b.adr = 0
            b.dat_w = 0
            b.cyc = 0
            b.sel = 0
            b.stb = 0
            b.we = 0

        @staticmethod
        def idle_mirror(b : WishboneInitiator):
            b.dat_r = 0
            b.err = 0
            b.ack = 0

    @zdc.dataclass
    class Initiator(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        wb_i : WishboneInitiator = zdc.field()
        _state : zdc.Int = zdc.field()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _initiator_proc(self):
            if (self.reset):
                self._state = 0
                WishboneInitiator.idle(self.wb_i)
            else:
                if self._state == 0:
                    self.wb_i.cyc = 1
                    self.wb_i.stb = 1
                    self._state = 1
                elif self._state == 1:
                    if self.wb_i.ack == 1:
                        self._state = 0

    @zdc.dataclass
    class Consumer(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        wb_t : WishboneInitiator = zdc.mirror()
        _state : zdc.Int = zdc.field()

        @zdc.sync(clock=lambda s:s.clock, reset=lambda s:s.reset)
        def _consumer_proc(self):
            if self.reset:
                self._state = 0
                WishboneInitiator.idle_mirror(self.wb_t)
            else:
                if self._state == 0:
                    self.wb_t.ack = 0
                    if self.wb_t.cyc and self.wb_t.stb:
                        self._state = 1
                elif self._state == 1:
                    self._state = 2
                elif self._state == 2:
                    self._state = 3
                elif self._state == 3:
                    self.wb_t.ack = 1

    @zdc.dataclass
    class Top(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        initiator : Initiator = zdc.field(bind=zdc.bind[Self,Initiator](lambda s,f:{
            f.clock : s.clock,
            f.reset : s.reset,
            f.wb_i : s.consumer.wb_t,
            
        }))

        consumer : Consumer = zdc.field()

        def __bind__(self) -> Optional[Dict]:
            return {
                self.initiator.clock : self.consumer.clock,
                self.initiator.reset : self.consumer.reset,
                self.initiator.wb_i : self.consumer.wb_t
            }
            pass

        @staticmethod
        def dobind(s : Top, i : Initiator) -> Dict:
            return {
            }

        consumer : Consumer = zdc.field(bind=zdc.bind[Self,Consumer](lambda s,i:{
            i.clock : s.clock,
            i.clock : s.reset,
        }))


