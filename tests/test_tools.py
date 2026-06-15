"""
tests/test_tools.py

Unit tests for each FitFindr tool, focusing on failure modes and return shapes.
Run with: pytest tests/
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter():
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_no_exception_on_impossible_query():
    # Should return [] gracefully, not raise
    result = search_listings("xyzzy completely made up item", size="ZZZZ", max_price=0.01)
    assert result == []


def test_search_result_fields():
    results = search_listings("denim", size=None, max_price=None)
    assert len(results) > 0
    item = results[0]
    for field in ("id", "title", "price", "platform", "size", "condition"):
        assert field in item


def test_search_sorted_by_relevance():
    # A very specific query should rank the best match first
    results = search_listings("levi jeans denim vintage", size=None, max_price=None)
    assert len(results) > 0
    # First result should mention levi or denim
    first = results[0]
    text = (first["title"] + first["description"] + " ".join(first["style_tags"])).lower()
    assert any(kw in text for kw in ["levi", "denim", "jean"])


# ── suggest_outfit ────────────────────────────────────────────────────────────

def test_suggest_outfit_with_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one result to test suggest_outfit"
    outfit = suggest_outfit(results[0], get_example_wardrobe())
    assert isinstance(outfit, str)
    assert len(outfit.strip()) > 0


def test_suggest_outfit_empty_wardrobe():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    outfit = suggest_outfit(results[0], get_empty_wardrobe())
    assert isinstance(outfit, str)
    assert len(outfit.strip()) > 0
    # Should not crash or return empty string


def test_suggest_outfit_returns_string_not_exception():
    # Pass a minimal item dict — should not raise even with odd input
    minimal_item = {
        "title": "Mystery Piece",
        "category": "tops",
        "colors": [],
        "style_tags": [],
        "description": "",
    }
    result = suggest_outfit(minimal_item, get_empty_wardrobe())
    assert isinstance(result, str)


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_empty_outfit():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    result = create_fit_card("", results[0])
    assert "Cannot generate" in result


def test_create_fit_card_whitespace_outfit():
    results = search_listings("jacket", size=None, max_price=None)
    assert results
    result = create_fit_card("   ", results[0])
    assert "Cannot generate" in result


def test_create_fit_card_returns_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results
    outfit_hint = "wear it with baggy jeans and chunky sneakers"
    card = create_fit_card(outfit_hint, results[0])
    assert isinstance(card, str)
    assert len(card.strip()) > 0


def test_create_fit_card_no_exception_on_missing_fields():
    # Minimal item dict — should not crash
    item = {"title": "Test Item", "price": 10, "platform": "depop"}
    result = create_fit_card("great outfit look", item)
    assert isinstance(result, str)
