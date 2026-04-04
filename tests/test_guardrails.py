"""
Unit and property-based tests for guardrails.py
Feature: aegis-enhanced-features
"""
import json
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, settings
from hypothesis import strategies as st

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guardrails import (
    validate_order_cost,
    validate_supplier_location,
    check_guardrails_for_order,
    check_guardrails_for_reroute,
)


# ── Unit Tests: validate_order_cost ───────────────────────────────────────────

def test_order_cost_blocked_above_threshold():
    """Req 7.5: cost > 10000 must be BLOCKED."""
    result = validate_order_cost(10001)
    assert result is not None
    assert result["status"] == "BLOCKED"


def test_order_cost_blocked_high_value():
    result = validate_order_cost(99999.99)
    assert result is not None
    assert result["status"] == "BLOCKED"


def test_order_cost_allowed_at_threshold():
    """Req 7.6: cost == 10000 must be allowed (None)."""
    result = validate_order_cost(10000)
    assert result is None


def test_order_cost_allowed_below_threshold():
    """Req 7.6: cost < 10000 must be allowed (None)."""
    result = validate_order_cost(9999.99)
    assert result is None


def test_order_cost_allowed_zero():
    result = validate_order_cost(0)
    assert result is None


# ── Unit Tests: validate_supplier_location ────────────────────────────────────

def _mock_supplier(location: str, status: str = "Active"):
    """Returns a mock sqlite3.Row-like object."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: {"location": location, "status": status, "supplier_id": "TEST"}[key]
    return row


def test_supplier_restricted_location_blocked():
    """Req 7.7: Restricted country supplier must be BLOCKED."""
    with patch("guardrails.get_connection") as mock_conn:
        cursor = MagicMock()
        cursor.fetchone.return_value = _mock_supplier("North Korea")
        mock_conn.return_value.__enter__ = MagicMock(return_value=MagicMock(cursor=lambda: cursor))
        mock_conn.return_value.cursor.return_value = cursor
        mock_conn.return_value.close = MagicMock()
        result = validate_supplier_location("S004")
    assert result is not None
    assert result["status"] == "BLOCKED"


def test_supplier_restricted_status_blocked():
    """Supplier with Restricted status must be BLOCKED."""
    with patch("guardrails.get_connection") as mock_conn:
        cursor = MagicMock()
        cursor.fetchone.return_value = _mock_supplier("Taiwan", "Restricted")
        mock_conn.return_value.cursor.return_value = cursor
        mock_conn.return_value.close = MagicMock()
        result = validate_supplier_location("S_RESTRICTED")
    assert result is not None
    assert result["status"] == "BLOCKED"


def test_supplier_active_non_restricted_allowed():
    """Req 7.9: Active supplier in non-restricted location must return None."""
    with patch("guardrails.get_connection") as mock_conn:
        cursor = MagicMock()
        cursor.fetchone.return_value = _mock_supplier("Germany", "Active")
        mock_conn.return_value.cursor.return_value = cursor
        mock_conn.return_value.close = MagicMock()
        result = validate_supplier_location("S002")
    assert result is None


# ── Unit Tests: check_guardrails_for_reroute ──────────────────────────────────

def test_reroute_always_blocked_active_supplier():
    """Req 7.8: Rerouting is always BLOCKED regardless of supplier."""
    with patch("guardrails.get_connection") as mock_conn:
        cursor = MagicMock()
        cursor.fetchone.return_value = _mock_supplier("USA", "Active")
        mock_conn.return_value.cursor.return_value = cursor
        mock_conn.return_value.close = MagicMock()
        result = check_guardrails_for_reroute("S003")
    assert result is not None
    data = json.loads(result)
    assert data["status"] == "BLOCKED"


# ── Property-Based Tests ──────────────────────────────────────────────────────

# Feature: aegis-enhanced-features, Property 17: Guardrail cost threshold
@given(cost=st.floats(min_value=10000.01, max_value=1e9, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_cost_above_threshold_always_blocked(cost):
    """Property 17: Any cost > 10000 must be BLOCKED."""
    result = validate_order_cost(cost)
    assert result is not None
    assert result["status"] == "BLOCKED"


# Feature: aegis-enhanced-features, Property 17: Guardrail cost threshold (lower bound)
@given(cost=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_property_cost_at_or_below_threshold_allowed(cost):
    """Property 17: Any cost <= 10000 must return None."""
    result = validate_order_cost(cost)
    assert result is None


# Feature: aegis-enhanced-features, Property 19: Reroute always blocked
@given(supplier_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
@settings(max_examples=50)
def test_property_reroute_always_blocked(supplier_id):
    """Property 19: check_guardrails_for_reroute must always return BLOCKED."""
    with patch("guardrails.get_connection") as mock_conn:
        cursor = MagicMock()
        cursor.fetchone.return_value = _mock_supplier("USA", "Active")
        mock_conn.return_value.cursor.return_value = cursor
        mock_conn.return_value.close = MagicMock()
        result = check_guardrails_for_reroute(supplier_id)
    assert result is not None
    data = json.loads(result)
    assert data["status"] == "BLOCKED"
