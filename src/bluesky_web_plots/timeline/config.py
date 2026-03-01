from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import attrs
from attrs import field

from .predicates import ConfigError, Predicate, parse_predicate, _err


class SourceName(str, Enum):
    TILED = "tiled"
    LIVE = "live"


class PanelKind(str, Enum):
    SUMMARY = "summary"
    RUN_METADATA = "run_metadata"
    STREAM_PLOT = "stream_plot"
    TABLE_PREVIEW = "table_preview"
    JSON_EDITOR = "json_editor"


def _as_bool(x: Any, *, path: str) -> bool:
    if isinstance(x, bool):
        return x
    raise _err(path, "must be boolean")


def _as_int(x: Any, *, path: str) -> int:
    if isinstance(x, int) and not isinstance(x, bool):
        return x
    raise _err(path, "must be integer")


def _as_number(x: Any, *, path: str) -> float:
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    raise _err(path, "must be number")


def _as_str(x: Any, *, path: str) -> str:
    if isinstance(x, str):
        return x
    raise _err(path, "must be string")


def _get_obj(d: Mapping[str, Any], key: str, *, path: str, required: bool = False) -> Mapping[str, Any]:
    if key not in d:
        if required:
            raise _err(path, f"missing required key '{key}'")
        return {}
    v = d[key]
    if not isinstance(v, Mapping):
        raise _err(f"{path}.{key}", "must be object")
    return v


def _get_list(d: Mapping[str, Any], key: str, *, path: str, required: bool = False) -> list[Any]:
    if key not in d:
        if required:
            raise _err(path, f"missing required key '{key}'")
        return []
    v = d[key]
    if not isinstance(v, list):
        raise _err(f"{path}.{key}", "must be list")
    return v


@attrs.define(frozen=True, slots=True)
class AppConfig:
    title: str = "Bluesky Run Browser"
    timezone: str = "UTC"

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "AppConfig":
        title = d.get("title", "Bluesky Run Browser")
        tz = d.get("timezone", "UTC")
        if not isinstance(title, str):
            raise _err(path + ".title", "must be string")
        if not isinstance(tz, str):
            raise _err(path + ".timezone", "must be string")
        return AppConfig(title=title, timezone=tz)


@attrs.define(frozen=True, slots=True)
class LiveSourceConfig:
    enabled: bool = True
    zmq_address: Optional[str] = None
    max_live_runs: int = 50
    max_live_event_pages_per_stream: int = 200

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "LiveSourceConfig":
        enabled = _as_bool(d.get("enabled", True), path=path + ".enabled")
        zmq_address = d.get("zmq_address")
        if enabled and (not isinstance(zmq_address, str) or not zmq_address):
            raise _err(path + ".zmq_address", "required when live.enabled is true")
        if zmq_address is not None and not isinstance(zmq_address, str):
            raise _err(path + ".zmq_address", "must be string")
        max_live_runs = _as_int(d.get("max_live_runs", 50), path=path + ".max_live_runs")
        max_pages = _as_int(d.get("max_live_event_pages_per_stream", 200), path=path + ".max_live_event_pages_per_stream")
        return LiveSourceConfig(
            enabled=enabled,
            zmq_address=zmq_address,
            max_live_runs=max_live_runs,
            max_live_event_pages_per_stream=max_pages,
        )


@attrs.define(frozen=True, slots=True)
class TiledSourceConfig:
    enabled: bool = True
    uri: Optional[str] = None
    root: str = "runs"
    poll_interval_ms: int = 2000
    lookback_hours: float = 48.0
    include_incomplete: bool = True

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "TiledSourceConfig":
        enabled = _as_bool(d.get("enabled", True), path=path + ".enabled")
        uri = d.get("uri")
        if enabled and (not isinstance(uri, str) or not uri):
            raise _err(path + ".uri", "required when tiled.enabled is true")
        if uri is not None and not isinstance(uri, str):
            raise _err(path + ".uri", "must be string")
        root = d.get("root", "runs")
        if not isinstance(root, str):
            raise _err(path + ".root", "must be string")
        poll = _as_int(d.get("poll_interval_ms", 2000), path=path + ".poll_interval_ms")
        lookback = _as_number(d.get("lookback_hours", 48.0), path=path + ".lookback_hours")
        include_incomplete = _as_bool(d.get("include_incomplete", True), path=path + ".include_incomplete")
        return TiledSourceConfig(
            enabled=enabled,
            uri=uri,
            root=root,
            poll_interval_ms=poll,
            lookback_hours=lookback,
            include_incomplete=include_incomplete,
        )


@attrs.define(frozen=True, slots=True)
class SourcesConfig:
    live: LiveSourceConfig
    tiled: TiledSourceConfig

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "SourcesConfig":
        live_d = _get_obj(d, "live", path=path, required=False)
        tiled_d = _get_obj(d, "tiled", path=path, required=False)
        return SourcesConfig(
            live=LiveSourceConfig.from_dict(live_d, path=path + ".live"),
            tiled=TiledSourceConfig.from_dict(tiled_d, path=path + ".tiled"),
        )


@attrs.define(frozen=True, slots=True)
class TimelineClipConfig:
    min_duration_ms: int = 5
    running_update_ms: int = 500

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "TimelineClipConfig":
        min_d = _as_int(d.get("min_duration_ms", 5), path=path + ".min_duration_ms")
        upd = _as_int(d.get("running_update_ms", 500), path=path + ".running_update_ms")
        return TimelineClipConfig(min_duration_ms=min_d, running_update_ms=upd)


@attrs.define(frozen=True, slots=True)
class TimelineShowConfig:
    live: bool = True
    tiled: bool = True

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "TimelineShowConfig":
        live = _as_bool(d.get("live", True), path=path + ".live")
        tiled = _as_bool(d.get("tiled", True), path=path + ".tiled")
        return TimelineShowConfig(live=live, tiled=tiled)


@attrs.define(frozen=True, slots=True)
class TimelineConfig:
    default_window_hours: float = 12.0
    show: TimelineShowConfig = field(factory=TimelineShowConfig)
    track_order: tuple[str, ...] = field(factory=tuple)
    clip: TimelineClipConfig = field(factory=TimelineClipConfig)

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "TimelineConfig":
        win = _as_number(d.get("default_window_hours", 12.0), path=path + ".default_window_hours")
        show = TimelineShowConfig.from_dict(_get_obj(d, "show", path=path, required=False), path=path + ".show")
        order_raw = d.get("track_order", [])
        if order_raw is None:
            order_raw = []
        if not isinstance(order_raw, list) or any(not isinstance(x, str) for x in order_raw):
            raise _err(path + ".track_order", "must be list of strings")
        clip = TimelineClipConfig.from_dict(_get_obj(d, "clip", path=path, required=False), path=path + ".clip")
        return TimelineConfig(default_window_hours=win, show=show, track_order=tuple(order_raw), clip=clip)


@attrs.define(frozen=True, slots=True)
class GroupBy:
    field: str
    fallback: str = ""

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "GroupBy":
        f = d.get("field")
        if not isinstance(f, str) or not f:
            raise _err(path + ".field", "must be non-empty string")
        fb = d.get("fallback", "")
        if not isinstance(fb, str):
            raise _err(path + ".fallback", "must be string")
        return GroupBy(field=f, fallback=fb)


@attrs.define(frozen=True, slots=True)
class TemplateSpec:
    template: str

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "TemplateSpec":
        t = d.get("template")
        if not isinstance(t, str):
            raise _err(path + ".template", "must be string")
        return TemplateSpec(template=t)


@attrs.define(frozen=True, slots=True)
class LabelSpec:
    title: Optional[TemplateSpec] = None
    subtitle: Optional[TemplateSpec] = None

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "LabelSpec":
        title = d.get("title")
        subtitle = d.get("subtitle")
        ts = None if title is None else TemplateSpec.from_dict(title, path=path + ".title")
        ss = None if subtitle is None else TemplateSpec.from_dict(subtitle, path=path + ".subtitle")
        return LabelSpec(title=ts, subtitle=ss)


@attrs.define(frozen=True, slots=True)
class PanelSpec:
    kind: PanelKind
    stream: Optional[str] = None
    fields: str = "hinted"
    rows: int = 50
    target: str = "config"

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "PanelSpec":
        kind_raw = d.get("kind")
        if not isinstance(kind_raw, str):
            raise _err(path + ".kind", "must be string")
        try:
            kind = PanelKind(kind_raw)
        except ValueError as e:
            raise _err(path + ".kind", f"unknown kind '{kind_raw}'") from e

        stream = d.get("stream")
        fields = d.get("fields", "hinted")
        rows = d.get("rows", 50)
        target = d.get("target", "config")

        if stream is not None and not isinstance(stream, str):
            raise _err(path + ".stream", "must be string")
        if not isinstance(fields, str):
            raise _err(path + ".fields", "must be string")
        if not isinstance(rows, int) or isinstance(rows, bool):
            raise _err(path + ".rows", "must be int")
        if not isinstance(target, str):
            raise _err(path + ".target", "must be string")

        # Validate required keys per kind
        if kind in (PanelKind.STREAM_PLOT, PanelKind.TABLE_PREVIEW) and not stream:
            raise _err(path + ".stream", f"required for kind '{kind.value}'")

        return PanelSpec(kind=kind, stream=stream, fields=fields, rows=rows, target=target)


@attrs.define(frozen=True, slots=True)
class SelectionSpec:
    left_panel: Optional[PanelSpec] = None
    right_panel: Optional[PanelSpec] = None

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "SelectionSpec":
        lp = d.get("left_panel")
        rp = d.get("right_panel")
        left = None if lp is None else PanelSpec.from_dict(lp, path=path + ".left_panel")
        right = None if rp is None else PanelSpec.from_dict(rp, path=path + ".right_panel")
        return SelectionSpec(left_panel=left, right_panel=right)


@attrs.define(frozen=True, slots=True)
class TrackConfig:
    id: str
    name: str

    include_sources: tuple[SourceName, ...] = field(factory=lambda: (SourceName.TILED, SourceName.LIVE))
    require_streams: tuple[str, ...] = field(factory=tuple)

    where: Predicate = field(factory=lambda: parse_predicate([], path="tracks[].where"))  # overwritten in from_dict
    group_by: Optional[GroupBy] = None
    label: Optional[LabelSpec] = None
    on_select: Optional[SelectionSpec] = None
    streams_hint: tuple[str, ...] = field(factory=tuple)

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "TrackConfig":
        tid = d.get("id")
        name = d.get("name")
        if not isinstance(tid, str) or not tid:
            raise _err(path + ".id", "must be non-empty string")
        if not isinstance(name, str) or not name:
            raise _err(path + ".name", "must be non-empty string")

        include_sources_raw = d.get("include_sources", ["tiled", "live"])
        if not isinstance(include_sources_raw, list) or any(not isinstance(x, str) for x in include_sources_raw):
            raise _err(path + ".include_sources", "must be list of strings")
        try:
            include_sources = tuple(SourceName(x) for x in include_sources_raw)
        except ValueError as e:
            raise _err(path + ".include_sources", "allowed values are 'tiled' and/or 'live'") from e
        if not include_sources:
            raise _err(path + ".include_sources", "must not be empty")

        require_streams_raw = d.get("require_streams", [])
        if not isinstance(require_streams_raw, list) or any(not isinstance(x, str) for x in require_streams_raw):
            raise _err(path + ".require_streams", "must be list of strings")

        where_raw = d.get("where", [])
        where = parse_predicate(where_raw, path=path + ".where")

        group_by = None
        if "group_by" in d and d["group_by"] is not None:
            gb_d = d["group_by"]
            if not isinstance(gb_d, Mapping):
                raise _err(path + ".group_by", "must be object")
            group_by = GroupBy.from_dict(gb_d, path=path + ".group_by")

        label = None
        if "label" in d and d["label"] is not None:
            lab_d = d["label"]
            if not isinstance(lab_d, Mapping):
                raise _err(path + ".label", "must be object")
            label = LabelSpec.from_dict(lab_d, path=path + ".label")

        on_select = None
        if "on_select" in d and d["on_select"] is not None:
            os_d = d["on_select"]
            if not isinstance(os_d, Mapping):
                raise _err(path + ".on_select", "must be object")
            on_select = SelectionSpec.from_dict(os_d, path=path + ".on_select")

        streams_hint_raw = d.get("streams_hint", [])
        if not isinstance(streams_hint_raw, list) or any(not isinstance(x, str) for x in streams_hint_raw):
            raise _err(path + ".streams_hint", "must be list of strings")

        return TrackConfig(
            id=tid,
            name=name,
            include_sources=include_sources,
            require_streams=tuple(require_streams_raw),
            where=where,
            group_by=group_by,
            label=label,
            on_select=on_select,
            streams_hint=tuple(streams_hint_raw),
        )


@attrs.define(frozen=True, slots=True)
class PanelsDefaults:
    left: PanelSpec = field(factory=lambda: PanelSpec(kind=PanelKind.SUMMARY))
    right: PanelSpec = field(factory=lambda: PanelSpec(kind=PanelKind.STREAM_PLOT, stream="primary"))

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "PanelsDefaults":
        left_d = d.get("left", {"kind": "summary"})
        right_d = d.get("right", {"kind": "stream_plot", "stream": "primary"})
        if not isinstance(left_d, Mapping):
            raise _err(path + ".left", "must be object")
        if not isinstance(right_d, Mapping):
            raise _err(path + ".right", "must be object")
        return PanelsDefaults(
            left=PanelSpec.from_dict(left_d, path=path + ".left"),
            right=PanelSpec.from_dict(right_d, path=path + ".right"),
        )


@attrs.define(frozen=True, slots=True)
class PanelsConfig:
    defaults: PanelsDefaults = field(factory=PanelsDefaults)

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str) -> "PanelsConfig":
        defaults_d = d.get("defaults", {})
        if not isinstance(defaults_d, Mapping):
            raise _err(path + ".defaults", "must be object")
        return PanelsConfig(defaults=PanelsDefaults.from_dict(defaults_d, path=path + ".defaults"))


@attrs.define(frozen=True, slots=True)
class RootConfig:
    version: int
    sources: SourcesConfig
    timeline: TimelineConfig
    tracks: tuple[TrackConfig, ...]
    app: AppConfig = field(factory=AppConfig)
    panels: PanelsConfig = field(factory=PanelsConfig)

    @staticmethod
    def from_dict(d: Mapping[str, Any], *, path: str = "root") -> "RootConfig":
        v = d.get("version")
        if v != 1:
            raise _err(path + ".version", "must be 1")

        app = AppConfig.from_dict(_get_obj(d, "app", path=path, required=False), path=path + ".app")

        sources_d = _get_obj(d, "sources", path=path, required=True)
        sources = SourcesConfig.from_dict(sources_d, path=path + ".sources")

        timeline_d = _get_obj(d, "timeline", path=path, required=True)
        timeline = TimelineConfig.from_dict(timeline_d, path=path + ".timeline")

        tracks_raw = _get_list(d, "tracks", path=path, required=True)
        tracks: list[TrackConfig] = []
        for i, t in enumerate(tracks_raw):
            if not isinstance(t, Mapping):
                raise _err(f"{path}.tracks[{i}]", "must be object")
            tracks.append(TrackConfig.from_dict(t, path=f"{path}.tracks[{i}]"))

        # Validate unique ids
        seen: set[str] = set()
        for t in tracks:
            if t.id in seen:
                raise _err(path + ".tracks", f"duplicate track id '{t.id}'")
            seen.add(t.id)

        panels = PanelsConfig.from_dict(_get_obj(d, "panels", path=path, required=False), path=path + ".panels")

        return RootConfig(
            version=1,
            app=app,
            sources=sources,
            timeline=timeline,
            tracks=tuple(tracks),
            panels=panels,
        )