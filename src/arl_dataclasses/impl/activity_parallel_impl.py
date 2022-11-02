
from .ctor import Ctor
from .modelinfo_activity import ModelinfoActivity

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
        scope_mi = ModelinfoActivity(scope_dt)
        print("Parallel.__enter__")
        ctor_a.add_activity(scope_ft)
        ctor_a.push_activity_scope_mi(scope_mi)

    def __exit__(self, t, v, tb):
        ctor_a = Ctor.inst()
        ctor_a.pop_activity_scope_mi()
        print("Parallel.__leave__")

    