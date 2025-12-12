from __future__ import annotations
import asyncio
import dataclasses as dc
import inspect
from typing import TYPE_CHECKING, Optional, List, Tuple
from ..types import Component
from ..decorators import ExecProc

if TYPE_CHECKING:
    from .obj_factory import ObjFactory
    from .timebase import Timebase


@dc.dataclass(kw_only=True)
class CompImplRT(object):
    _factory : ObjFactory = dc.field()
    _name : str = dc.field()
    _parent : Component = dc.field()
    _timebase_inst : Optional[Timebase] = dc.field(default=None)
    _processes : List[Tuple[str, ExecProc]] = dc.field(default_factory=list)
    _tasks : List[asyncio.Task] = dc.field(default_factory=list)
    _processes_started : bool = dc.field(default=False)

    @property
    def name(self) -> str:
        return self._name
    
    @property
    def parent(self) -> Component:
        return self._parent

    def timebase(self) -> Timebase:
        """Return the timebase, inheriting from parent if not set."""
        if self._timebase_inst is not None:
            return self._timebase_inst
        if self._parent is not None:
            return self._parent._impl.timebase()
        raise RuntimeError("No timebase available")

    def set_timebase(self, tb: Timebase):
        """Set the timebase for this component."""
        self._timebase_inst = tb

    def add_process(self, name: str, proc: ExecProc):
        """Register a process to be started."""
        self._processes.append((name, proc))

    def start_processes(self, comp: Component):
        """Start all registered processes for this component."""
        for name, proc in self._processes:
            task = asyncio.create_task(proc.method(comp))
            self._tasks.append(task)

    def start_all_processes(self, comp: Component):
        """Recursively start all processes in the component tree."""
        if self._processes_started:
            return
        self._processes_started = True
        
        # Start processes for child components first
        for f in dc.fields(comp):
            fo = getattr(comp, f.name)
            if isinstance(fo, Component):
                fo._impl.start_all_processes(fo)
        
        # Start processes for this component
        self.start_processes(comp)

    def post_init(self, comp):
        from .obj_factory import ObjFactory
        print("--> CompImpl.post_init")

        for f in dc.fields(comp):
            fo = getattr(comp, f.name)

            if inspect.isclass(f.type) and issubclass(f.type, Component): # and not f.init:
                print("Comp Field: %s" % f.name)
                if hasattr(fo, "_impl"):
                    fo._impl.post_init(fo)
                    print("Has impl")
                pass
        print("<-- CompImpl.post_init")

#        self.name = self.factory.name_s[-1]


    def build(self, factory):
        pass

    def shutdown(self):
        """Cancel all running process tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        self._tasks.clear()

    async def wait(self, comp: Component, amt = None):
        """
        Uses the default timebase to suspend execution of the
        calling coroutine for the specified time.
        
        When called and simulation is not already running, this also 
        drives the simulation forward.
        """
        from ..types import Time
        tb = self.timebase()
        
        if not tb._running:
            # Simulation not running: find root and drive simulation
            root = comp
            while root._impl.parent is not None:
                root = root._impl.parent
            root._impl.start_all_processes(root)
            await tb.run_until(amt)
        else:
            # Inside simulation: just wait for the specified time
            await tb.wait(amt)

    def time(self):
        """Returns the current time"""
        from ..types import Time
        tb = self.timebase()
        return tb.time()

    pass