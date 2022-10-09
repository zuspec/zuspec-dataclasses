
from .ctor import Ctor


from .activity_scope_impl import ActivityScopeImpl
class ActivitySequenceImpl(ActivityScopeImpl):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pass

    def __enter__(self):
        ctor_a = Ctor.inst()
        scope_dt = ctor_a.ctxt().mkDataTypeActivitySequence()
        scope_ft = ctor_a.ctxt().mkTypeFieldActivity(
            "",
            scope_dt,
            True)
        ctor_a.activity_scope().addActivity(scope_ft)
        ctor_a.push_activity_scope(scope_dt)
        pass

    def __exit__(self, t, v, tb):
        ctor_a = Ctor.inst()
        ctor_a.pop_activity_scope()
        pass
