
import zsp_dataclasses.impl as impl
import vsc_dataclasses.impl as vsc_impl
from unittest import TestCase


class TestBase(TestCase):

    def setUp(self) -> None:
        ctxt = impl.pyctxt.context.Context()
        impl.Ctor.init(ctxt)
        vsc_impl.Ctor.init(ctxt)
        
        
        return super().setUp()

    pass