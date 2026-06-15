"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query.

    Uses regex to find size tokens (e.g., "size M", "size XL", or standalone
    "size S/M") and price limits (e.g., "under $30", "under 40").
    Everything remaining after removing those tokens is treated as the description.
    """
    text = query

    # Extract max_price: "under $30" or "under 30"
    max_price = None
    price_match = re.search(r"under\s+\$?(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if price_match:
        max_price = float(price_match.group(1))
        text = text[:price_match.start()] + text[price_match.end():]

    # Extract size: "size M", "size S/M", "size XL", or standalone tokens like "M", "XL", "W28"
    size = None
    size_match = re.search(
        r"\bsize\s+([A-Za-z0-9/]+)\b",
        text,
        re.IGNORECASE,
    )
    if size_match:
        size = size_match.group(1)
        text = text[:size_match.start()] + text[size_match.end():]
    else:
        # Try standalone size tokens: XS, S, M, L, XL, XXL, W28, W30, etc.
        standalone = re.search(r"\b(XXS|XS|XL|XXL|S/M|M/L|[SMLX]{1,3}|W\d{2})\b", text)
        if standalone:
            size = standalone.group(1)
            text = text[:standalone.start()] + text[standalone.end():]

    # Everything left (stripped of filler words) is the description
    # Remove common filler phrases
    filler = re.compile(
        r"\b(i'm looking for|looking for|i want|find me|i need|"
        r"i mostly wear|i wear|my style is|what's out there|"
        r"how would i style it|and|in a|in|a|an|the)\b",
        re.IGNORECASE,
    )
    description = filler.sub(" ", text).strip()
    description = re.sub(r"\s{2,}", " ", description).strip(" ,.")

    if not description:
        description = query  # fallback: use the full query

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
        wardrobe: User's wardrobe dict

    Returns:
        The session dict. Check session["error"] first — if not None,
        the interaction ended early and outfit_suggestion/fit_card will be None.
    """
    session = _new_session(query, wardrobe)

    # Step 2: Parse query
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search listings
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        size_info = f", size {parsed['size']}" if parsed["size"] else ""
        price_info = f", max ${parsed['max_price']:.0f}" if parsed["max_price"] else ""
        session["error"] = (
            f"No listings found for \"{parsed['description']}\""
            f"{size_info}{price_info}. "
            "Try broader search terms, remove the size filter, or raise your price limit."
        )
        return session

    # Step 4: Select top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit
    outfit = suggest_outfit(session["selected_item"], session["wardrobe"])
    session["outfit_suggestion"] = outfit

    if outfit.startswith("Error"):
        session["error"] = outfit
        return session

    # Step 6: Create fit card
    fit_card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    session["fit_card"] = fit_card

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
