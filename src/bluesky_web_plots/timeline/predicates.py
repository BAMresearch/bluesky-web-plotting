from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence, Union, Optional, Iterable

import attrs
from attrs import field


class ConfigError(ValueError):
    """Raised when config parsing/validation fails."""


def _err(path: str, msg: str) -> ConfigError:
    return ConfigError(f"{path}: {msg}")


def resolve_field_path(ctx: Mapping[str, Any], path: str) -> Any:
    """
    Resolve dot-separated field path like 'start.plan_name' against ctx.

    ctx roots: uid, start, stop, streams
    Missing path => None
    """
    parts = path.split(".")
    cur: Any = ctx
    for p in parts:
        if isinstance(cur, Mapping) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur


@attrs.define(frozen=True, slots=True)
class RelativeTime:
    """
    Represents a relative time offset like '-24h' evaluated against 'now'.
    """
    spec: str

    def to_epoch_seconds(self, now: Optional[datetime] = None) -> float:
        if now is None:
            now = datetime.now(timezone.utc)

        s = self.spec.strip()
        if not s:
            raise ValueError("empty relative time spec")

        sign = -1
        if s[0] == "+":
            sign = +1
            s = s[1:]
        elif s[0] == "-":
            sign = -1
            s = s[1:]
        else:
            # default: treat as negative? No—force explicit sign to avoid surprises
            raise ValueError("relative spec must start with '+' or '-' (e.g. '-24h')")

        unit = s[-1]
        num_str = s[:-1]
        try:
            num = float(num_str)
        except ValueError as e:
            raise ValueError(f"invalid relative number '{num_str}'") from e

        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(unit)
        if mult is None:
            raise ValueError("invalid relative unit; use one of s,m,h,d")

        return now.timestamp() + sign * (num * mult)


class Op(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NIN = "nin"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EXISTS = "exists"
    MISSING = "missing"
    NOT_EMPTY = "not_empty"
    CONTAINS = "contains"
    REGEX = "regex"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


@attrs.define(frozen=True, slots=True)
class LeafPredicate:
    field: str
    op: Op
    value: Any = None

    def evaluate(self, ctx: Mapping[str, Any], *, now: Optional[datetime] = None) -> bool:
        v = resolve_field_path(ctx, self.field)

        # Handle relative value objects like {"relative": "-24h"}
        rhs = self.value
        if isinstance(rhs, Mapping) and "relative" in rhs:
            rhs = RelativeTime(str(rhs["relative"])).to_epoch_seconds(now=now)

        if self.op == Op.EXISTS:
            return v is not None
        if self.op == Op.MISSING:
            return v is None
        if self.op == Op.NOT_EMPTY:
            if isinstance(v, str):
                return len(v) > 0
            if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
                return len(v) > 0
            return False

        # For string ops, require string
        if self.op in (Op.CONTAINS, Op.REGEX, Op.STARTS_WITH, Op.ENDS_WITH):
            if not isinstance(v, str):
                return False
            if not isinstance(rhs, str):
                return False
            if self.op == Op.CONTAINS:
                return rhs in v
            if self.op == Op.STARTS_WITH:
                return v.startswith(rhs)
            if self.op == Op.ENDS_WITH:
                return v.endswith(rhs)
            if self.op == Op.REGEX:
                import re
                return re.search(rhs, v) is not None

        # IN/NIN expects iterable rhs
        if self.op in (Op.IN, Op.NIN):
            if not isinstance(rhs, Sequence) or isinstance(rhs, (str, bytes, bytearray)):
                return False
            ok = v in rhs
            return ok if self.op == Op.IN else (not ok)

        # Numeric/time comparisons
        if self.op in (Op.GT, Op.GTE, Op.LT, Op.LTE, Op.EQ, Op.NEQ):
            # Equality works on anything (including None)
            if self.op == Op.EQ:
                return v == rhs
            if self.op == Op.NEQ:
                return v != rhs

            # For ordering comparisons, require comparable scalars
            try:
                if v is None or rhs is None:
                    return False
                if self.op == Op.GT:
                    return v > rhs
                if self.op == Op.GTE:
                    return v >= rhs
                if self.op == Op.LT:
                    return v < rhs
                if self.op == Op.LTE:
                    return v <= rhs
            except TypeError:
                return False

        # Should be unreachable if op list is exhaustive
        return False


@attrs.define(frozen=True, slots=True)
class AllPredicate:
    items: tuple["Predicate", ...] = field(converter=tuple)

    def evaluate(self, ctx: Mapping[str, Any], *, now: Optional[datetime] = None) -> bool:
        return all(p.evaluate(ctx, now=now) for p in self.items)


@attrs.define(frozen=True, slots=True)
class AnyPredicate:
    items: tuple["Predicate", ...] = field(converter=tuple)

    def evaluate(self, ctx: Mapping[str, Any], *, now: Optional[datetime] = None) -> bool:
        return any(p.evaluate(ctx, now=now) for p in self.items)


@attrs.define(frozen=True, slots=True)
class NotPredicate:
    item: "Predicate"

    def evaluate(self, ctx: Mapping[str, Any], *, now: Optional[datetime] = None) -> bool:
        return not self.item.evaluate(ctx, now=now)


Predicate = Union[LeafPredicate, AllPredicate, AnyPredicate, NotPredicate]


def parse_predicate(obj: Any, *, path: str) -> Predicate:
    """
    Parse a Predicate from config JSON.

    Supported forms:
      - leaf: {"field": "...", "op": "...", "value": ...}
      - {"all": [ ... ]}
      - {"any": [ ... ]}
      - {"not": { ... }}
    """
    if obj is None:
        # Treat null as "no filter" -> always true
        return AllPredicate(items=())

    if not isinstance(obj, Mapping):
        raise _err(path, "predicate must be an object")

    if "all" in obj:
        items = obj["all"]
        if not isinstance(items, list):
            raise _err(path + ".all", "must be a list")
        return AllPredicate(tuple(parse_predicate(x, path=f"{path}.all[{i}]") for i, x in enumerate(items)))

    if "any" in obj:
        items = obj["any"]
        if not isinstance(items, list):
            raise _err(path + ".any", "must be a list")
        return AnyPredicate(tuple(parse_predicate(x, path=f"{path}.any[{i}]") for i, x in enumerate(items)))

    if "not" in obj:
        return NotPredicate(parse_predicate(obj["not"], path=path + ".not"))

    # leaf
    if "field" not in obj or "op" not in obj:
        raise _err(path, "leaf predicate requires 'field' and 'op'")

    field_path = obj["field"]
    op_raw = obj["op"]
    if not isinstance(field_path, str) or not field_path:
        raise _err(path + ".field", "must be a non-empty string")
    if not isinstance(op_raw, str):
        raise _err(path + ".op", "must be a string")

    try:
        op = Op(op_raw)
    except ValueError as e:
        raise _err(path + ".op", f"unknown operator '{op_raw}'") from e

    value = obj.get("value")
    # Validate presence/absence of "value" for ops
    needs_value = op not in (Op.EXISTS, Op.MISSING, Op.NOT_EMPTY)
    if needs_value and "value" not in obj:
        raise _err(path, f"operator '{op.value}' requires 'value'")
    if (not needs_value) and ("value" in obj):
        # Allowed but discouraged; you can turn this into a hard error if you prefer
        pass

    return LeafPredicate(field=field_path, op=op, value=value)
