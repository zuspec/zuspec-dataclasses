
import zuspec.impl as impl
import vsc_dataclasses.impl as vsc_impl
from unittest import TestCase
from zuspec.impl.pyctxt.context import Context


class TestBase(TestCase):

    def setUp(self) -> None:
        ctxt = Context()
        impl.Ctor.init(ctxt)
        vsc_impl.Ctor.init(ctxt)
        
        
        return super().setUp()

    pass