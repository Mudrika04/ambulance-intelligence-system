from __future__ import annotations

from app.core.types import Approach, Zone
from app.decision.roi import ROIManager, point_in_polygon


def test_point_in_polygon():
    square = [(0, 0), (1, 0), (1, 1), (0, 1)]
    assert point_in_polygon(0.5, 0.5, square)
    assert not point_in_polygon(1.5, 0.5, square)


def test_north_approach_detected(cfg):
    roi = ROIManager(cfg)
    res = roi.classify(0.5 * 960, 0.1 * 540, 960, 540)
    assert res.approach == Approach.NORTH.value
    assert res.in_roi


def test_zone_tightens_near_the_centre(cfg):
    roi = ROIManager(cfg)
    far = roi.classify(0.5 * 960, 0.02 * 540, 960, 540)
    near = roi.classify(0.5 * 960, 0.5 * 540, 960, 540)
    assert far.normalised_distance > near.normalised_distance
    assert near.zone in (Zone.CONTROL_ZONE.value, Zone.CLEARANCE_ZONE.value)


def test_unknown_approach_outside_every_polygon(cfg):
    roi = ROIManager(cfg)
    res = roi.classify(0.05 * 960, 0.05 * 540, 960, 540)
    assert res.approach == Approach.UNKNOWN.value
    assert not res.in_roi


def test_roi_geometry_is_configurable(cfg):
    cfg.set("roi.approaches", {"NORTH": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]})
    roi = ROIManager(cfg)
    assert roi.classify(10, 10, 960, 540).approach == "NORTH"
