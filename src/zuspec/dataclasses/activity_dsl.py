"""Activity DSL stub functions for use inside ``async def activity(self)``.

These functions are **never executed at runtime**.  They exist solely so that
Python can parse and import files containing activity bodies without error.
The ``@zdc.dataclass`` decorator captures the source of ``activity()`` methods
via ``inspect.getsource()`` and walks the AST; the stubs provide the
necessary names in the module namespace.

If any stub is accidentally called at runtime an informative ``RuntimeError``
is raised.

Typical import (via ``zuspec.dataclasses``)::

    import zuspec.dataclasses as zdc

    @zdc.dataclass
    class MyAction(zdc.Action[MyComp]):
        a: WriteAction
        b: ReadAction

        async def activity(self):
            await self.a()
            with zdc.parallel():
                await zdc.do(WriteAction)
                await self.b()
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional, Type


_MSG = (
    "{name}() is an activity DSL function.  "
    "It must only appear inside 'async def activity(self)' bodies, "
    "which are parsed from AST and never executed directly."
)


def do(action_type: Type[Any], /) -> Any:
    """Traverse an action by type (anonymous traversal).

    PSS equivalent: ``do ActionType;``

    Always ``await`` this call — action traversal is asynchronous::

        await do(WriteAction)

        with do(WriteAction) as wr:
            wr.size > 16

        xfer = await do(WriteAction)   # labeled, no constraints
    """
    raise RuntimeError(_MSG.format(name="do"))


class _ActivityCtx:
    """Sentinel context manager returned by activity DSL stubs.

    Never enters; raises if used outside an AST-parsed activity.
    """
    def __enter__(self) -> '_ActivityCtx':
        raise RuntimeError(
            "Activity DSL context managers must only appear inside "
            "'async def activity(self)' bodies, which are parsed from AST."
        )

    def __exit__(self, *args: Any) -> None:
        pass

    # Support ``with do(T) as x:`` — enter() returns self so ``as`` binding works
    # when the parser synthesises the AST.  At runtime this is unreachable.
    def __iter__(self) -> Iterator['_ActivityCtx']:
        return iter([self])


def parallel(
    *,
    join_branch: Optional[str] = None,
    join_none: bool = False,
    join_select: Optional[int] = None,
    join_first: Optional[int] = None,
) -> _ActivityCtx:
    """Parallel scheduling block.

    PSS equivalent: ``parallel [join_spec] { ... }``

    Join specifications (at most one)::

        with parallel():                         # join all (default)
        with parallel(join_branch='L2'):          # join specific branch
        with parallel(join_none=True):            # no join
        with parallel(join_select=1):             # join N random branches
        with parallel(join_first=1):              # join first N to finish
    """
    return _ActivityCtx()


def schedule(
    *,
    join_branch: Optional[str] = None,
    join_none: bool = False,
    join_select: Optional[int] = None,
    join_first: Optional[int] = None,
) -> _ActivityCtx:
    """Schedule block — arbitrary ordering with optional join spec.

    PSS equivalent: ``schedule [join_spec] { ... }``
    """
    return _ActivityCtx()


def sequence() -> _ActivityCtx:
    """Explicit sequential block.

    PSS equivalent: ``sequence { ... }``

    Statements execute in order (same as the default activity body semantics).
    """
    return _ActivityCtx()


def atomic() -> _ActivityCtx:
    """Atomic block — all children execute as an indivisible unit.

    PSS equivalent: ``atomic { ... }``
    """
    return _ActivityCtx()


def select() -> _ActivityCtx:
    """Select statement — exactly one branch is chosen.

    PSS equivalent: ``select { ... }``

    Must contain one or more ``with branch():`` blocks::

        with select():
            with branch(weight=70):
                do(ActionA)
            with branch(guard=self.x > 0, weight=30):
                do(ActionB)
    """
    return _ActivityCtx()


def branch(
    *,
    guard: Any = None,
    weight: Any = None,
) -> _ActivityCtx:
    """One branch of a ``select`` block.

    Args:
        guard:  Boolean expression — branch is only eligible when true.
        weight: Integer expression — relative selection weight.
    """
    return _ActivityCtx()


def do_while(condition: Any, /) -> _ActivityCtx:
    """Do-while loop — body executes at least once, then condition checked.

    PSS equivalent: ``repeat { ... } while (cond);``::

        with do_while(self.s1.last_one != 0):
            self.s1()
    """
    return _ActivityCtx()


def while_do(condition: Any, /) -> _ActivityCtx:
    """While-do loop — condition checked first, then body executes.

    Not present in the PSS LRM but supported for Python-native patterns.

        with while_do(self.remaining > 0):
            do(ProcessAction)
    """
    return _ActivityCtx()


def replicate(count: Any, /, *, label: Optional[str] = None) -> Any:
    """Replicate construct — expand N copies into the enclosing scope.

    Unlike ``range()``, ``replicate()`` does not introduce a sequential loop;
    copies inherit the scheduling semantics of the enclosing block.

    PSS equivalent: ``replicate (N) [label[]:] { ... }``::

        with parallel():
            for i in replicate(self.count):
                do(ActionA)
                do(ActionB)
    """
    raise RuntimeError(_MSG.format(name="replicate"))


def constraint() -> _ActivityCtx:
    """Scheduling constraint block — constrains relationships between sub-actions.

    PSS equivalent: inline constraint block inside an activity::

        with constraint():
            self.a1.size + self.a2.size < 100
            self.a1.addr != self.a2.addr
    """
    return _ActivityCtx()


def bind(src: Any, dst: Any, /) -> None:
    """Explicit flow-object binding between sub-action ports.

    PSS equivalent: ``bind src dst;``::

        bind(self.producer.data_out, self.consumer.data_in)
    """
    raise RuntimeError(_MSG.format(name="bind"))


__all__ = [
    "do",
    "parallel",
    "schedule",
    "sequence",
    "atomic",
    "select",
    "branch",
    "do_while",
    "while_do",
    "replicate",
    "constraint",
    "bind",
]
