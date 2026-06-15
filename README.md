# FitFindr

A multi-tool AI agent that helps users find secondhand pieces and figure out how to wear them. Given a natural language query, FitFindr searches a mock thrift listings dataset, suggests outfit combinations using the user's wardrobe, and generates a shareable Instagram-style fit card — all in a single interaction.

---

## Setup

```bash
git clone <your-fork-url>
cd fitfindr
python3 -m venv .venv
source .venv/bin/activate      # Mac/Linux
pip install -r requirements.txt

# Create .env with your Groq key (free at console.groq.com):
echo "GROQ_API_KEY=your_key_here" > .env

python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`

Searches the mock listings dataset for secondhand items. Filters by `max_price` (inclusive) and `size` (case-insensitive substring match), then scores each remaining listing by keyword overlap between `description` and the listing's title, description, style_tags, category, colors, and brand fields. Returns a list of matching listing dicts sorted by score (best match first), or `[]` if nothing matches. Never raises an exception.

Each returned dict contains: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str|None), `platform` (str).

### `suggest_outfit(new_item: dict, wardrobe: dict) → str`

Calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfit combinations. If `wardrobe['items']` is non-empty, the prompt names specific wardrobe pieces in the suggestions. If the wardrobe is empty, the LLM provides general styling advice about types of pieces that pair well with the new item. Returns a non-empty string in all cases.

### `create_fit_card(outfit: str, new_item: dict) → str`

Generates a 2–4 sentence Instagram/TikTok-style caption for the outfit. Uses LLM temperature 1.2 to ensure variety across calls. Mentions the item name, price, and platform naturally. Guards against empty `outfit` input — returns an error message string immediately without calling the LLM.

---

## How the Planning Loop Works

`run_agent()` in `agent.py` proceeds through four steps, with a hard branch at step 2:

1. **Parse query** — regex extracts `description`, `size`, and `max_price` from the user's natural language input. Filler phrases ("looking for", "I mostly wear") are stripped to isolate the item description.

2. **Search listings** — calls `search_listings()`. **Branch:** if results are empty, `session["error"]` is set to a helpful message and the function returns immediately. `suggest_outfit` and `create_fit_card` are never called with empty input.

3. **Suggest outfit** — calls `suggest_outfit()` with `session["selected_item"]` (the top search result) and `session["wardrobe"]`. If the response starts with "Error", the session error is set and the loop returns early.

4. **Create fit card** — calls `create_fit_card()` with `session["outfit_suggestion"]` and `session["selected_item"]`. Returns the completed session.

The agent does not call all three tools in a fixed unconditional sequence — it halts at step 2 when search returns no results.

---

## State Management

All state lives in a single `session` dict initialized by `_new_session()`. Key fields and when they're written:

| Field | When written | Used by |
|---|---|---|
| `query` | initialization | parsing |
| `parsed` | after query parsing | `search_listings` |
| `search_results` | after `search_listings` | selecting `selected_item` |
| `selected_item` | after non-empty results | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | initialization (passed in) | `suggest_outfit` |
| `outfit_suggestion` | after `suggest_outfit` | `create_fit_card` |
| `fit_card` | after `create_fit_card` | UI display |
| `error` | on any early termination | UI display |

The session dict is the single handoff mechanism. `app.py`'s `handle_query()` reads `session["selected_item"]`, `session["outfit_suggestion"]`, and `session["fit_card"]` to populate the three Gradio output panels.

---

## Error Handling

| Tool | Failure mode | Agent response |
|---|---|---|
| `search_listings` | No results match the query | Sets `session["error"]` to `"No listings found for '<description>' (size: X, max: $Y). Try broader search terms, remove the size filter, or raise your price limit."` Returns session immediately — `suggest_outfit` and `create_fit_card` are not called. |
| `suggest_outfit` | Wardrobe is empty | Prompts LLM for general styling advice instead of wardrobe-specific combos. Returns a non-empty string. Example: querying with `get_empty_wardrobe()` returns general advice about what types of pieces pair well. |
| `create_fit_card` | `outfit` is empty or whitespace-only | Returns `"Cannot generate a fit card without an outfit suggestion."` immediately, without calling the LLM. |

**Concrete tested example:** Running `python3 -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"` returns `[]` with no exception. Running `python3 -c "from tools import create_fit_card, search_listings; r = search_listings('tee', None, 50); print(create_fit_card('', r[0]))"` returns the error message string `"Cannot generate a fit card without an outfit suggestion."`.

---

## Spec Reflection

**One way the spec helped:** Writing out the conditional logic in the Planning Loop section before coding made it clear that `suggest_outfit` must never receive `None` as its first argument. That forced an explicit early-return branch in `run_agent()` rather than letting a `None` propagate into the LLM prompt silently.

**One way implementation diverged from the spec:** The spec described parsing `size` as a simple regex on `"size M"` patterns. In practice, the listings data uses sizes like `"S/M"`, `"XL (oversized)"`, and `"W30 L30"` — so an additional fallback regex for standalone size tokens (XXS, XS, S/M, W28, etc.) was added. The planning.md described only the `size\s+\S+` pattern; the implementation added a second `re.search` pass to catch common standalone tokens.

---

## AI Usage

**Instance 1 — `search_listings` implementation:**
I gave Claude the Tool 1 spec block from planning.md (inputs, return value, failure mode, the instruction to use `load_listings()`) along with the field list from the docstring. I asked it to implement keyword overlap scoring across title, description, style_tags, category, colors, and brand. The generated code scored only against title and style_tags. I overrode it to also score against description and colors, which improved results for color-based queries like "rust corduroy" and "black combat boots."

**Instance 2 — `run_agent()` planning loop:**
I gave Claude the Architecture diagram from planning.md and asked it to implement `run_agent()` following the numbered TODO steps in agent.py. The generated code placed the empty-results branch after `selected_item` was already assigned, which meant a `None` could slip through if the branch logic misfired. I moved the early-return check to immediately after `search_results` is set and before `selected_item` is assigned, to match the spec's branching sequence.
