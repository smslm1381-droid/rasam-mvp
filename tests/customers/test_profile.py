"""تست پروفایل مشتری و ساخت گراف بر اساس قابلیت‌ها."""

from __future__ import annotations

from pathlib import Path

import pytest

from rasam import config, customer
from rasam.core import graph

ROOT = config.CUSTOMERS_DIR
# پروفایل‌هایی که فقط برای تست‌اند، کنار مشتری‌های واقعی نمی‌نشینند.
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "customers"


def test_demo_profile_contains_configuration_without_a_secret():
    profile = customer.load_profile("demo", ROOT)
    assert profile.db_type == "mongodb"
    assert profile.connection_env == "MONGO_URI"
    assert "inverter_data" in profile.allowed_collections
    assert "chart" in profile.capabilities
    assert profile.limits["max_rows"] == 1000


def test_profiles_build_different_graphs():
    chart_graph = graph.build_graph(customer.load_profile("demo", ROOT).capabilities)
    plain_graph = graph.build_graph(customer.load_profile("no_chart", FIXTURES).capabilities)
    assert "chart" in chart_graph.nodes
    assert "chart" not in plain_graph.nodes


def test_missing_profile_is_rejected(tmp_path):
    with pytest.raises(customer.ProfileError, match="پیدا نشد"):
        customer.load_profile("missing", tmp_path)