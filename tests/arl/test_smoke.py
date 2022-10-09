
from .test_base import TestBase
import arl_dataclasses as arl

class TestSmoke(TestBase):

    def test_smoke(self):

        @arl.action
        class MyAction(object):
            pass

        pass