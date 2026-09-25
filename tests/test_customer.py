"""تست پروفایل مشتری و ساخت گراف بر اساس قابلیت‌ها."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import customer  # noqa: E402
import graph  # noqa: E402


ROOT = Path(__file__).resolve().parents[1] / "customers"


def test_demo_profile_contains_configuration_without_a_secret():
    profile = customer.load_profile("demo", ROOT)
    assert profile.db_type == "mongodb"
    assert profile.connection_env == "MONGO_URI"
    assert "inverter_data" in profile.allowed_collections
    assert "chart" in profile.capabilities
    assert profile.limits["max_rows"] == 1000


def test_profiles_build_different_graphs():
    chart_graph = graph.build_graph(customer.load_profile("demo", ROOT).capabilities)
    plain_graph = graph.build_graph(customer.load_profile("no_chart", ROOT).capabilities)
    assert "chart" in chart_graph.nodes
    assert "chart" not in plain_graph.nodes


def test_missing_profile_is_rejected(tmp_path):
    with pytest.raises(customer.ProfileError, match="پیدا نشد"):
        customer.load_profile("missing", tmp_path)