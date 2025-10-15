import zuspec.dataclasses as zdc

def test_smoke():

    @zdc.dataclass
    class MyFSM(zdc.Component):
        clock : zdc.Bit = zdc.input()
        reset : zdc.Bit = zdc.input()
        adv : zdc.Bit = zdc.input()

        # Need to bind clock, reset, and init
        # Associations must be done via function
        # Keep type independent?
        _ctrl : zdc.FSM = zdc.fsm(
            clock=lambda s:s.clock,
            reset=lambda s:s.reset,
            initial=lambda s:s.init
        )

        @zdc.fsm.state
        def init(self):
            if self.adv:
                self._ctrl.state = self.s1
            pass

        @zdc.fsm.state
        def s1(self):
            if self.adv:
                self._ctrl.state = self.s2
            pass

        @zdc.fsm.state
        def s2(self):
            if self.adv:
                self._ctrl.state = self.init
            pass




