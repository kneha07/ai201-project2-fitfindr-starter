"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _llm(prompt: str, temperature: float = 0.7) -> str:
    """Call Groq llama-3.3-70b-versatile and return the response text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    try:
        listings = load_listings()
    except Exception:
        return []

    # Apply hard filters first
    filtered = []
    for item in listings:
        if max_price is not None and item.get("price", 0) > max_price:
            continue
        if size is not None:
            item_size = (item.get("size") or "").lower()
            if size.lower() not in item_size:
                continue
        filtered.append(item)

    # Score by keyword overlap against searchable text fields
    keywords = description.lower().split()

    def score(item: dict) -> int:
        text_parts = [
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
            item.get("brand", "") or "",
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
        ]
        haystack = " ".join(text_parts).lower()
        return sum(1 for kw in keywords if kw in haystack)

    scored = [(score(item), item) for item in filtered]
    scored = [(s, item) for s, item in scored if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key. May be empty.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice.
    """
    try:
        item_desc = (
            f"Item: {new_item.get('title', 'Unknown')}\n"
            f"Category: {new_item.get('category', '')}\n"
            f"Colors: {', '.join(new_item.get('colors', []))}\n"
            f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
            f"Description: {new_item.get('description', '')}"
        )

        wardrobe_items = wardrobe.get("items", [])

        if not wardrobe_items:
            prompt = (
                f"A user just found this thrifted piece:\n{item_desc}\n\n"
                "They don't have a wardrobe on file yet. Suggest 1–2 complete outfit ideas "
                "for this item. Be specific about the types of pieces that would work (e.g., "
                "high-waisted wide-leg jeans, chunky sneakers, a fitted ribbed tank). "
                "Describe the vibe or aesthetic of each look in 1–2 sentences."
            )
        else:
            wardrobe_text = "\n".join(
                f"- {w.get('name', '')} ({w.get('category', '')})"
                + (f": {w['notes']}" if w.get("notes") else "")
                for w in wardrobe_items
            )
            prompt = (
                f"A user just found this thrifted piece:\n{item_desc}\n\n"
                f"Their current wardrobe:\n{wardrobe_text}\n\n"
                "Suggest 1–2 complete outfit combinations using the new item and specific "
                "pieces from their wardrobe. Name the wardrobe pieces by their exact names. "
                "Describe the vibe or styling approach for each look in 1–2 sentences."
            )

        return _llm(prompt, temperature=0.8)

    except Exception as e:
        return f"Error generating outfit suggestion: {e}"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message string.
    """
    if not outfit or not outfit.strip():
        return "Cannot generate a fit card without an outfit suggestion."

    try:
        title = new_item.get("title", "thrifted piece")
        price = new_item.get("price", "?")
        platform = new_item.get("platform", "a thrift app")
        style_tags = ", ".join(new_item.get("style_tags", []))

        prompt = (
            f"Write a 2–4 sentence Instagram caption for this thrifted outfit.\n\n"
            f"Item found: {title} — ${price} on {platform}\n"
            f"Style vibes: {style_tags}\n"
            f"Outfit: {outfit}\n\n"
            "Rules:\n"
            "- Sound like a real person posting an OOTD, not a product description\n"
            "- Mention the item name, price, and platform naturally (each only once)\n"
            "- Be specific about the outfit vibe — not generic\n"
            "- Casual, lowercase tone is fine; a relevant emoji or two is fine\n"
            "- 2–4 sentences max\n"
            "Write only the caption, nothing else."
        )

        return _llm(prompt, temperature=1.2)

    except Exception as e:
        return f"Error generating fit card: {e}"
