
from .test_base import TestBase
import zuspec as arl

class TestSmoke(TestBase):

    def test_smoke(self):

        @arl.action
        class MyAction(object):
            pass

        pass