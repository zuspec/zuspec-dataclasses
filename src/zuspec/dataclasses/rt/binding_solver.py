"""Head-action AllDifferent solver for parallel blocks.

Before spawning parallel branches, assigns distinct resource instance_id
values to each branch's first action's lock fields, guaranteeing no two
branches start with the same resource held.
"""
from __future__ import annotations

import dataclasses as dc
import random
from typing import TYPE_CHECKING, Any

from .resource_rt import get_resource_fields

if TYPE_CHECKING:
    from .action_context import ActionContext


@dc.dataclass
class HeadAssignment:
    """Per-branch result from BindingSolver."""
    branch_index: int
    resource_hints: dict[str, int]  # field_name → instance_id


class BindingSolver:
    """Solves resource assignments for parallel head actions.

    Uses random sampling from the feasible pool domain to give each parallel
    branch a distinct resource instance (AllDifferent constraint).
    """

    def solve_heads(
        self,
        head_action_types: list[type],
        ctx: "ActionContext",
    ) -> list[HeadAssignment]:
        """Return one HeadAssignment per branch with distinct instance_id values
        across all lock fields that draw from the same pool.
        """
        # Group entries by pool: id(pool) → [(branch_index, field_name, pool, domain)]
        pool_groups: dict[int, list[tuple]] = {}
        for bi, action_type in enumerate(head_action_types):
            for fi in get_resource_fields(action_type):
                if fi.claim != "lock":
                    continue
                pool = ctx.pool_resolver.resolve_pool_by_type(
                    action_type, fi.name, ctx.comp
                )
                if pool is None:
                    continue
                resources = getattr(pool, "resources", None) or getattr(pool, "items", None) or []
                domain = list(range(len(resources)))
                pool_groups.setdefault(id(pool), []).append(
                    (bi, fi.name, pool, domain)
                )

        # Assign distinct instance_ids per pool group via random permutation
        assignments: dict[int, dict[str, int]] = {
            i: {} for i in range(len(head_action_types))
        }
        rng = random.Random(ctx.seed)

        for entries in pool_groups.values():
            _, _, pool, domain = entries[0]
            n_claims = len(entries)
            if n_claims > len(domain):
                raise RuntimeError(
                    f"Pool has {len(domain)} instance(s) but {n_claims} "
                    f"concurrent lock claims — binding is infeasible"
                )
            chosen = rng.sample(domain, k=n_claims)
            for (bi, field_name, _, _), instance_id in zip(entries, chosen):
                assignments[bi][field_name] = instance_id

        return [
            HeadAssignment(branch_index=i, resource_hints=assignments[i])
            for i in range(len(head_action_types))
        ]
