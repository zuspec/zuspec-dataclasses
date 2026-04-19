"""Runtime enforcement of ``with zdc.requires:`` / ``with zdc.ensures:`` contracts.

This module provides :class:`ContractChecker`, which wraps async body methods
to check pre-/postconditions extracted by
:meth:`~zuspec.dataclasses.constraint_parser.ConstraintParser.extract_method_contracts`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Dict

if TYPE_CHECKING:
    from .action_context import ActionContext


_SENTINEL = object()


def _get_body_contracts(action_type: type) -> Dict[str, List]:
    """Return (and cache) the parsed contract expressions for *action_type*.body.

    Returns a dict with keys ``'requires'`` and ``'ensures'``, each a list of
    parsed expression dicts (possibly empty).  The result is cached on the
    function object so parsing happens at most once per class.
    """
    body_fn = action_type.__dict__.get('body')
    if body_fn is None:
        return {'requires': [], 'ensures': []}

    cached = getattr(body_fn, '_contract_requires', _SENTINEL)
    if cached is not _SENTINEL:
        return {
            'requires': body_fn._contract_requires,
            'ensures':  body_fn._contract_ensures,
        }

    # Parse and cache
    try:
        from ..constraint_parser import ConstraintParser
        contracts = ConstraintParser().extract_method_contracts(body_fn)
    except Exception:
        contracts = {'requires': [], 'ensures': []}

    body_fn._contract_requires = contracts['requires']
    body_fn._contract_ensures  = contracts['ensures']
    return contracts


def check_body_contracts(action_type: type, action: Any, ctx: "ActionContext", role: str) -> None:
    """Evaluate all *role* contract expressions for *action_type*.body.

    Raises :class:`~zuspec.dataclasses.decorators.ContractViolation` on the
    first expression that evaluates to ``False``.

    Args:
        action_type: The action class (used to look up the body method).
        action:      The instantiated action object (fields are bound).
        ctx:         The :class:`ActionContext` for expression evaluation.
        role:        ``'requires'`` or ``'ensures'``.
    """
    contracts = _get_body_contracts(action_type)
    exprs = contracts.get(role, [])
    if not exprs:
        return

    from ..decorators import ContractViolation
    from .expr_eval import ExprEval

    evaluator = ExprEval(ctx)
    for expr in exprs:
        result = evaluator.eval(expr)
        if not result:
            raise ContractViolation(
                role=role,
                method_name=f"{action_type.__name__}.body",
                expr_repr=str(expr),
            )


class ContractChecker:
    """Wraps async method calls to enforce requires/ensures contracts.

    Contracts are parsed from ``with zdc.requires:`` / ``with zdc.ensures:``
    blocks inside the method body (see P4 / :meth:`ConstraintParser.extract_method_contracts`).
    When *check_contracts* is ``False`` (the default), wrapping is a no-op and
    overhead is zero.
    """

    def __init__(self, check_contracts: bool = False) -> None:
        self._enabled = check_contracts

    def wrap(self, method, instance, ctx: "ActionContext"):
        """Return a coroutine that checks contracts around *method* on *instance*.

        If *check_contracts* is ``False``, returns the plain bound method.
        """
        if not self._enabled:
            return method.__get__(instance)

        requires_exprs = getattr(method, '_contract_requires', _SENTINEL)
        if requires_exprs is _SENTINEL:
            # Parse and cache on the function
            try:
                from ..constraint_parser import ConstraintParser
                contracts = ConstraintParser().extract_method_contracts(method)
            except Exception:
                contracts = {'requires': [], 'ensures': []}
            method._contract_requires = contracts['requires']
            method._contract_ensures  = contracts['ensures']
            requires_exprs = method._contract_requires

        ensures_exprs = method._contract_ensures

        bound = method.__get__(instance)

        async def _wrapped(*args, **kwargs):
            if requires_exprs:
                self._check_exprs(requires_exprs, 'requires', method.__name__, ctx)
            result = await bound(*args, **kwargs)
            if ensures_exprs:
                self._check_exprs(ensures_exprs, 'ensures', method.__name__, ctx)
            return result

        return _wrapped

    def _check_exprs(
        self,
        exprs: List,
        role: str,
        method_name: str,
        ctx: "ActionContext",
    ) -> None:
        from ..decorators import ContractViolation
        from .expr_eval import ExprEval

        evaluator = ExprEval(ctx)
        for expr in exprs:
            if not evaluator.eval(expr):
                raise ContractViolation(role, method_name, str(expr))
