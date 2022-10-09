
from .ctor import Ctor

class ActivityParallelImpl(object):

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        ctor_a = Ctor.inst()
        scope_dt = ctor_a.ctxt().mkDataTypeActivityParallel()
        scope_ft = ctor_a.ctxt().mkTypeFieldActivity(
            "",
            scope_dt,
            True)
        ctor_a.activity_scope().addActivity(scope_ft)
        ctor_a.push_activity_scope(scope_dt)

    def __exit__(self, t, v, tb):
        ctor_a = Ctor.inst()
        ctor_a.pop_activity_scope()

    