"""routing.py -- the caused-routing SPINE (Task A).

The research loop is split into (a) a creative PROPOSER (stub or Gemini or random
search) and (b) a deterministic ROUTING POLICY that converts past verdicts into
BINDING CONSTRAINTS on the next proposal. Every proposer flows through the policy,
which is what makes routing *caused* and *replayable* (offline, no API).

TWO LAYERS:
  Layer 1 (here) -- deterministic policy, a PURE FUNCTION of past verdicts:
     * a family that returned OVERFIT  -> BANNED (never propose again)
     * a family that returned FRAGILE once -> next proposal must TIGHTEN
       (freeze knobs, lengthen IS, shrink grid); a SECOND FRAGILE -> ABANDON
     * when every family of a KIND is blocked -> the kind is exhausted, route to a
       DIFFERENT kind of edge (trend <-> mean_reversion)
     * all families blocked -> STOP, report best ROBUST
  Layer 2 (in research.py / gemini_researcher.py) -- the metric-grounded lesson
     text is carried into the next proposal as a constraint; the model conditions
     its next move on its own prior, numbers-grounded reasoning.

`derive_constraints(history)` is the pure policy. `enforce(proposal, constraints)`
repairs or rejects any proposal that violates the active constraints; both the stub
and Gemini call it. This module measures the ablation (Task C): memory-ON = proposer
INTERSECT enforce; memory-OFF = proposer alone.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from itertools import product

import strategies as st

# tightening knobs applied to a FRAGILE family's next proposal
TIGHTEN_MIN_IS_YEARS = 6        # lengthen the in-sample window
TIGHTEN_MAX_COMBOS = 6          # shrink the grid
TIGHTEN_MAX_PARAMS_VARIED = 2   # freeze all but N knobs
GLOBAL_MAX_COMBOS = 36          # hygiene cap on every proposal


@dataclass
class Constraints:
    """The binding output of the policy for the NEXT proposal."""
    banned_families: list[str] = field(default_factory=list)      # OVERFIT
    abandoned_families: list[str] = field(default_factory=list)   # FRAGILE x2
    tighten_families: list[str] = field(default_factory=list)     # FRAGILE x1
    blocked_families: list[str] = field(default_factory=list)     # banned + abandoned
    available_families: list[str] = field(default_factory=list)   # proposable
    exhausted_kinds: list[str] = field(default_factory=list)
    preferred_kind: str | None = None
    action: str = "baseline"                                      # baseline|tighten|abandon|diversify
    caused_by: int | None = None
    carried_lesson: str | None = None
    stop: bool = False
    min_is_years: int = TIGHTEN_MIN_IS_YEARS
    max_combos: int = TIGHTEN_MAX_COMBOS
    max_params_varied: int = TIGHTEN_MAX_PARAMS_VARIED

    def to_journal(self) -> dict:
        """The subset persisted to the journal `constraints` field."""
        return {"banned_families": list(self.banned_families),
                "tighten_families": list(self.tighten_families),
                "preferred_kind": self.preferred_kind,
                "min_is_years": self.min_is_years,
                "max_combos": self.max_combos}


def _kinds_to_families() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for fam, kind in st.KINDS.items():
        out.setdefault(kind, []).append(fam)
    return out


def derive_constraints(history: list) -> Constraints:
    """Pure policy: past verdicts -> binding constraints. No randomness, no I/O."""
    overfit: set[str] = set()
    fragile: dict[str, int] = {}
    for h in history:
        fam, v = h["template"], h["verdict"]
        if v == "OVERFIT":
            overfit.add(fam)
        elif v == "FRAGILE":
            fragile[fam] = fragile.get(fam, 0) + 1

    banned = sorted(overfit)
    abandoned = sorted(f for f, c in fragile.items() if c >= 2 and f not in overfit)
    tighten = sorted(f for f, c in fragile.items() if c == 1 and f not in overfit and f not in abandoned)
    blocked = sorted(set(banned) | set(abandoned))
    available = [f for f in st.TEMPLATES if f not in blocked]

    k2f = _kinds_to_families()
    exhausted_kinds = sorted(k for k, fams in k2f.items() if all(f in blocked for f in fams))

    c = Constraints(
        banned_families=banned, abandoned_families=abandoned, tighten_families=tighten,
        blocked_families=blocked, available_families=available, exhausted_kinds=exhausted_kinds,
    )

    if not available:
        c.stop = True
        c.action = "abandon"
        return c

    if not history:
        c.action, c.caused_by, c.carried_lesson = "baseline", None, None
        c.preferred_kind = st.KINDS[available[0]]
        return c

    last = history[-1]
    last_fam, last_v = last["template"], last["verdict"]
    last_kind = st.KINDS[last_fam]
    c.caused_by = last["iteration"]
    c.carried_lesson = last.get("llm_lesson") or last.get("lesson")

    same_kind_available = [f for f in available if st.KINDS[f] == last_kind]
    other_kind_available = [f for f in available if st.KINDS[f] != last_kind]

    if last_v == "ROBUST":
        # found an edge; if the loop continues, branch out to a different kind
        c.action = "diversify"
        c.caused_by = None
        c.preferred_kind = (st.KINDS[other_kind_available[0]] if other_kind_available
                            else st.KINDS[available[0]])
    elif last_v == "FRAGILE" and fragile.get(last_fam, 0) == 1:
        # first stumble on this family -> tighten it (same family)
        c.action = "tighten"
        c.preferred_kind = last_kind
    else:
        # OVERFIT, or a family abandoned after a 2nd FRAGILE -> leave it
        if other_kind_available and (last_kind in exhausted_kinds or not same_kind_available):
            c.action = "diversify"
            c.preferred_kind = st.KINDS[other_kind_available[0]]
        elif same_kind_available:
            c.action = "abandon"
            c.preferred_kind = last_kind
        else:
            c.action = "diversify"
            c.preferred_kind = st.KINDS[available[0]]
    return c


# --- grid surgery ----------------------------------------------------------

def _n_combos(grid: dict, fam: str) -> int:
    valid = st.TEMPLATES[fam].get("valid")
    return sum(1 for _ in _combos(grid, valid))


def _combos(grid: dict, valid=None):
    keys = list(grid)
    for values in product(*(grid[k] for k in keys)):
        params = dict(zip(keys, values))
        if valid is None or valid(params):
            yield params


def _cap_combos(grid: dict, fam: str, max_combos: int) -> dict:
    """Trim the widest parameter until the valid-combo count fits under max_combos."""
    g = {k: list(v) for k, v in grid.items()}
    while _n_combos(g, fam) > max_combos:
        k = max(g, key=lambda k: len(g[k]))
        if len(g[k]) <= 1:
            break
        g[k] = g[k][:-1]
    return g


def _tighten_grid(grid: dict, fam: str, max_varied: int, max_combos: int) -> dict:
    """Freeze all but `max_varied` knobs (keep a central value), then cap combos."""
    items = sorted(grid.items(), key=lambda kv: len(kv[1]), reverse=True)
    out, varied = {}, 0
    for k, vals in items:
        vals = list(vals)
        if len(vals) > 1 and varied < max_varied:
            out[k] = vals
            varied += 1
        else:
            out[k] = [vals[len(vals) // 2]]          # central, deterministic freeze
    # restore original key order for legibility
    out = {k: out[k] for k in grid}
    return _cap_combos(out, fam, max_combos)


def default_grid(fam: str) -> dict:
    return {k: list(v) for k, v in st.TEMPLATES[fam]["grid"].items()}


def pick_family(constraints: Constraints) -> str | None:
    """Choose an available family honoring preferred_kind (deterministic)."""
    if not constraints.available_families:
        return None
    if constraints.preferred_kind:
        for f in constraints.available_families:
            if st.KINDS[f] == constraints.preferred_kind:
                return f
    return constraints.available_families[0]


def enforce(proposal: dict, constraints: Constraints) -> dict | None:
    """Repair/reject a proposal against the active constraints. Returns the (possibly
    rerouted + tightened) proposal, or None to STOP. Both stub and Gemini call this."""
    if constraints.stop or not constraints.available_families:
        return None

    p = copy.deepcopy(proposal)
    fam = p["template"]

    # 1. blocked (or unknown) family -> reroute to an available family of the preferred kind
    if fam not in st.TEMPLATES or fam in constraints.blocked_families:
        target = pick_family(constraints)
        if target is None:
            return None
        fam = target
        p["template"] = fam
        p["grid"] = default_grid(fam)
        p.setdefault("rerouted_from", proposal.get("template"))

    # 2. tighten family -> freeze knobs + lengthen IS
    if fam in constraints.tighten_families:
        p["grid"] = _tighten_grid(p.get("grid") or default_grid(fam), fam,
                                  constraints.max_params_varied, constraints.max_combos)
        w = dict(p.get("windows") or {"is_years": 4, "oos_years": 2, "step_years": 2})
        w["is_years"] = max(int(w.get("is_years", 4)), constraints.min_is_years)
        p["windows"] = w

    # 3. global hygiene: a valid, bounded grid is guaranteed
    grid = {k: list(v) for k, v in (p.get("grid") or default_grid(fam)).items()}
    grid = {k: v for k, v in grid.items() if k in st.TEMPLATES[fam]["grid"]}
    for k, v in st.TEMPLATES[fam]["grid"].items():
        grid.setdefault(k, list(v))
    grid = _cap_combos(grid, fam, GLOBAL_MAX_COMBOS)
    if _n_combos(grid, fam) == 0:
        grid = default_grid(fam)
    p["grid"] = grid
    return p
