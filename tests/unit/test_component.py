
import pytest 
import zuspec.dataclasses as zdc

def test_init_down():

    class MyComp(zdc.Component):

        def init_down(self):
            print("init_down")
            pass
        pass

