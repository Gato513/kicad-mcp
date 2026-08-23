"""Tests unitarios directos del cluster de geometría pura (DT1 slice 2, sesión 42).

Mitigación del riesgo S4 declarado en
``docs/analisis/42-dt1-slice2-caracterizacion.md`` §6: ninguna de las 13
funciones de ``tools/pcb_geometry.py`` tenía un test que la nombrara antes
de esta sesión — se ejercitaban solo indirectamente vía las tools que las
consumen (``add_track``, ``get_tracks``, ``delete_tracks_bulk``,
``get_footprint_neighbors``). Son funciones puras (sin I/O, sin ``bridge``,
sin excepciones de dominio): estos tests las llaman directamente con casos
mínimos, no a través del servidor MCP.
"""

from __future__ import annotations

import pytest

from kicad_mcp.bridge.ipc import BBoxMm, CopperItem, Mm, PadGeom
from kicad_mcp.tools.pcb_geometry import (
    _bbox_distance_to_point,
    _closest_board_edge,
    _closest_point_copper_bbox,
    _copper_distance_mm,
    _copper_distance_to_bbox,
    _copper_in_bbox,
    _copper_on_layer,
    _dist_point_segment,
    _dist_segment_to_pad,
    _find_track_pad_collision,
    _match_copper,
    _rounded_rect_sdf,
    _segment_intersects_bbox,
)


def _track(
    kiid: str = "T1",
    net: str = "GND",
    layer: str = "F.Cu",
    sx: float = 0.0,
    sy: float = 0.0,
    ex: float = 10.0,
    ey: float = 0.0,
) -> CopperItem:
    return CopperItem(
        kind="track",
        kiid=kiid,
        net_name=net,
        layer=layer,
        start_x_mm=Mm(sx),
        start_y_mm=Mm(sy),
        end_x_mm=Mm(ex),
        end_y_mm=Mm(ey),
        mid_x_mm=None,
        mid_y_mm=None,
    )


def _arc(
    kiid: str = "A1",
    net: str = "GND",
    layer: str = "F.Cu",
    sx: float = 0.0,
    sy: float = 0.0,
    mx: float = 5.0,
    my: float = 0.0,
    ex: float = 10.0,
    ey: float = 0.0,
) -> CopperItem:
    return CopperItem(
        kind="arc",
        kiid=kiid,
        net_name=net,
        layer=layer,
        start_x_mm=Mm(sx),
        start_y_mm=Mm(sy),
        end_x_mm=Mm(ex),
        end_y_mm=Mm(ey),
        mid_x_mm=Mm(mx),
        mid_y_mm=Mm(my),
    )


def _via(
    kiid: str = "V1",
    net: str = "GND",
    x: float = 5.0,
    y: float = 5.0,
    via_layers: tuple[str, str] | None = ("F.Cu", "B.Cu"),
) -> CopperItem:
    return CopperItem(
        kind="via",
        kiid=kiid,
        net_name=net,
        layer=None,
        start_x_mm=Mm(x),
        start_y_mm=Mm(y),
        end_x_mm=None,
        end_y_mm=None,
        mid_x_mm=None,
        mid_y_mm=None,
        via_layers=via_layers,
    )


def _pad(
    net: str | None = "SIG",
    layer: str = "F.Cu",
    x: float = 0.0,
    y: float = 0.0,
    w: float = 2.0,
    h: float = 2.0,
    rotation: float = 0.0,
    corner_ratio: float = 0.0,
) -> PadGeom:
    return PadGeom(
        net_name=net,
        layer=layer,
        x_mm=Mm(x),
        y_mm=Mm(y),
        w_mm=Mm(w),
        h_mm=Mm(h),
        rotation_deg=rotation,
        corner_ratio=corner_ratio,
    )


class TestDistPointSegment:
    def test_point_on_segment(self) -> None:
        assert _dist_point_segment(5.0, 0.0, 0.0, 0.0, 10.0, 0.0) == pytest.approx(0.0)

    def test_point_perpendicular(self) -> None:
        assert _dist_point_segment(5.0, 3.0, 0.0, 0.0, 10.0, 0.0) == pytest.approx(3.0)

    def test_point_past_endpoint_clamps(self) -> None:
        assert _dist_point_segment(15.0, 0.0, 0.0, 0.0, 10.0, 0.0) == pytest.approx(5.0)

    def test_degenerate_segment_is_point_distance(self) -> None:
        assert _dist_point_segment(3.0, 4.0, 0.0, 0.0, 0.0, 0.0) == pytest.approx(5.0)


class TestCopperDistanceMm:
    def test_via_distance_to_center(self) -> None:
        assert _copper_distance_mm(_via(x=0.0, y=0.0), 3.0, 4.0) == pytest.approx(5.0)

    def test_track_distance_to_segment(self) -> None:
        assert _copper_distance_mm(_track(sx=0, sy=0, ex=10, ey=0), 5.0, 3.0) == pytest.approx(3.0)

    def test_arc_distance_is_min_of_subsegments(self) -> None:
        arc = _arc(sx=0.0, sy=0.0, mx=5.0, my=0.0, ex=10.0, ey=0.0)
        assert _copper_distance_mm(arc, 2.0, 1.0) == pytest.approx(1.0)


class TestMatchCopper:
    def test_single_match_within_tolerance(self) -> None:
        items = (_track(kiid="T1", sx=0, sy=0, ex=10, ey=0),)
        target, candidates = _match_copper(
            items, 5.0, 0.1, kinds=("track", "arc"), tolerance_mm=0.5
        )
        assert target is not None
        assert target.kiid == "T1"
        assert candidates == [target]

    def test_ambiguous_match_returns_none_with_candidates(self) -> None:
        items = (
            _track(kiid="T1", sx=0, sy=0, ex=10, ey=0),
            _track(kiid="T2", sx=0, sy=0.2, ex=10, ey=0.2),
        )
        target, candidates = _match_copper(items, 5.0, 0.1, kinds=("track",), tolerance_mm=0.5)
        assert target is None
        assert {c.kiid for c in candidates} == {"T1", "T2"}

    def test_no_match_outside_tolerance(self) -> None:
        items = (_track(kiid="T1", sx=0, sy=0, ex=10, ey=0),)
        target, candidates = _match_copper(items, 5.0, 5.0, kinds=("track",), tolerance_mm=0.5)
        assert target is None
        assert candidates == []


class TestBboxDistanceToPoint:
    def test_point_inside_is_zero(self) -> None:
        assert _bbox_distance_to_point((0.0, 0.0, 10.0, 10.0), 5.0, 5.0) == pytest.approx(0.0)

    def test_point_outside(self) -> None:
        assert _bbox_distance_to_point((0.0, 0.0, 10.0, 10.0), 13.0, 4.0) == pytest.approx(3.0)


class TestCopperDistanceToBbox:
    def test_crossing_segment_is_zero(self) -> None:
        track = _track(sx=-5.0, sy=5.0, ex=15.0, ey=5.0)
        assert _copper_distance_to_bbox(track, (0.0, 0.0, 10.0, 10.0)) == pytest.approx(0.0)

    def test_segment_outside_bbox(self) -> None:
        track = _track(sx=20.0, sy=5.0, ex=30.0, ey=5.0)
        assert _copper_distance_to_bbox(track, (0.0, 0.0, 10.0, 10.0)) == pytest.approx(10.0)


class TestClosestPointCopperBbox:
    def test_returns_nearest_endpoint(self) -> None:
        track = _track(sx=-5.0, sy=5.0, ex=20.0, ey=5.0)
        point = _closest_point_copper_bbox(track, (0.0, 0.0, 10.0, 10.0))
        assert point == pytest.approx((-5.0, 5.0))


class TestClosestBoardEdge:
    def test_nearest_side_and_distance(self) -> None:
        board_bbox = BBoxMm(min_x=Mm(0.0), min_y=Mm(0.0), max_x=Mm(100.0), max_y=Mm(50.0))
        side, dist = _closest_board_edge((5.0, 20.0, 15.0, 30.0), board_bbox)
        assert side == "left"
        assert dist == pytest.approx(5.0)


class TestSegmentIntersectsBbox:
    def test_crossing_segment(self) -> None:
        assert _segment_intersects_bbox(-5.0, 5.0, 15.0, 5.0, (0.0, 0.0, 10.0, 10.0)) is True

    def test_non_crossing_segment(self) -> None:
        assert _segment_intersects_bbox(-5.0, 20.0, 15.0, 20.0, (0.0, 0.0, 10.0, 10.0)) is False

    def test_endpoint_inside(self) -> None:
        assert _segment_intersects_bbox(5.0, 5.0, 20.0, 20.0, (0.0, 0.0, 10.0, 10.0)) is True


class TestCopperInBbox:
    def test_via_inside(self) -> None:
        assert _copper_in_bbox(_via(x=5.0, y=5.0), (0.0, 0.0, 10.0, 10.0)) is True

    def test_via_outside(self) -> None:
        assert _copper_in_bbox(_via(x=50.0, y=50.0), (0.0, 0.0, 10.0, 10.0)) is False

    def test_track_crossing(self) -> None:
        track = _track(sx=-5.0, sy=5.0, ex=15.0, ey=5.0)
        assert _copper_in_bbox(track, (0.0, 0.0, 10.0, 10.0)) is True


class TestCopperOnLayer:
    def test_via_spans_layer(self) -> None:
        via = _via(via_layers=("F.Cu", "B.Cu"))
        assert _copper_on_layer(via, "F.Cu") is True
        assert _copper_on_layer(via, "In1.Cu") is False

    def test_track_matches_own_layer_only(self) -> None:
        track = _track(layer="F.Cu")
        assert _copper_on_layer(track, "F.Cu") is True
        assert _copper_on_layer(track, "B.Cu") is False


class TestRoundedRectSdf:
    def test_center_is_negative_distance_to_nearest_edge(self) -> None:
        assert _rounded_rect_sdf(0.0, 0.0, hw=2.0, hh=1.0, r=0.0) == pytest.approx(-1.0)

    def test_point_outside_axis_aligned(self) -> None:
        assert _rounded_rect_sdf(10.0, 0.0, hw=2.0, hh=1.0, r=0.0) == pytest.approx(8.0)

    def test_boundary_is_zero(self) -> None:
        assert _rounded_rect_sdf(2.0, 0.0, hw=2.0, hh=1.0, r=0.0) == pytest.approx(0.0)


class TestDistSegmentToPad:
    def test_segment_touching_pad_edge_is_zero(self) -> None:
        pad = _pad(x=5.0, y=0.0, w=2.0, h=2.0)
        # segmento horizontal a y=1: tangente al borde superior del pad
        # (hh=1), toca sin invadir.
        assert _dist_segment_to_pad(0.0, 1.0, 10.0, 1.0, pad) == pytest.approx(0.0, abs=1e-6)

    def test_segment_far_from_pad(self) -> None:
        pad = _pad(x=5.0, y=0.0, w=2.0, h=2.0)
        dist = _dist_segment_to_pad(0.0, 10.0, 10.0, 10.0, pad)
        assert dist == pytest.approx(9.0, abs=1e-6)


class TestFindTrackPadCollision:
    def test_same_net_pad_is_excluded(self) -> None:
        pads = (_pad(net="GND", x=5.0, y=0.0, w=2.0, h=2.0),)
        collision = _find_track_pad_collision(
            pads,
            net="GND",
            layer="F.Cu",
            width_mm=0.25,
            start_x_mm=0.0,
            start_y_mm=0.0,
            end_x_mm=10.0,
            end_y_mm=0.0,
            clearance_mm=0.2,
        )
        assert collision is None

    def test_other_net_pad_within_clearance_is_collision(self) -> None:
        pads = (_pad(net="SIG", x=5.0, y=0.0, w=2.0, h=2.0),)
        collision = _find_track_pad_collision(
            pads,
            net="GND",
            layer="F.Cu",
            width_mm=0.25,
            start_x_mm=0.0,
            start_y_mm=0.0,
            end_x_mm=10.0,
            end_y_mm=0.0,
            clearance_mm=0.2,
        )
        assert collision is not None
        assert collision.net_name == "SIG"

    def test_other_layer_non_passing_pad_is_ignored(self) -> None:
        pads = (_pad(net="SIG", layer="B.Cu", x=5.0, y=0.0, w=2.0, h=2.0),)
        collision = _find_track_pad_collision(
            pads,
            net="GND",
            layer="F.Cu",
            width_mm=0.25,
            start_x_mm=0.0,
            start_y_mm=0.0,
            end_x_mm=10.0,
            end_y_mm=0.0,
            clearance_mm=0.2,
        )
        assert collision is None
