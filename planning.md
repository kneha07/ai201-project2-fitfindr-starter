# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for secondhand items that match a natural language description, optional size filter, and optional price ceiling. Returns a ranked list of matching listing dicts sorted by relevance score.

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., "vintage graphic tee"). Used to score listings by keyword overlap with title, description, style_tags, category, and colors fields.
- `size` (str | None): Size string to filter by (e.g., "M", "W28"). Case-insensitive substring match against listing's size field. None means no size filter.
- `max_price` (float | None): Maximum price inclusive. None means no price filter.

**What it returns:**
A list of listing dicts, sorted by relevance score (highest first). Each dict contains: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str|None), `platform` (str). Returns an empty list `[]` when nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a human-readable message explaining what was searched and suggesting the user try broader terms (remove size filter, raise price limit). The agent returns the session immediately without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted item and the user's wardrobe, calls the Groq LLM to suggest 1–2 complete outfit combinations using specific pieces from the wardrobe or general style guidance if the wardrobe is empty.

**Input parameters:**
- `new_item` (dict): A listing dict (the item the user is considering buying). Used fields: title, description, style_tags, colors, category, condition.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: id, name, category, colors, style_tags, notes. May be empty.

**What it returns:**
A non-empty string with outfit suggestions. If wardrobe is populated, names specific wardrobe pieces in each outfit combo. If wardrobe is empty, gives general styling advice about what types of items pair well with the new piece and what vibe it suits.

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, the LLM is prompted for general styling advice rather than crashing or returning an empty string. If the LLM call raises an exception, the function catches it and returns an error message string describing what went wrong.

---

### Tool 3: create_fit_card

**What it does:**
Generates a 2–4 sentence Instagram/TikTok-style caption for the complete outfit, mentioning the thrifted item's price and platform naturally. Uses higher LLM temperature for variety.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit()`. Must be non-empty.
- `new_item` (dict): The listing dict for the thrifted item. Used fields: title, price, platform, style_tags, colors.

**What it returns:**
A 2–4 sentence casual caption string that feels authentic (like a real OOTD post), mentions the item name, price, and platform once each, and captures the outfit vibe in specific terms. Each call with different inputs should produce noticeably different output.

**What happens if it fails or returns nothing:**
If `outfit` is an empty or whitespace-only string, immediately returns a descriptive error message string ("Cannot generate a fit card without an outfit suggestion.") without calling the LLM. If the LLM call fails, catches the exception and returns an error message string.

---

### Additional Tools (if any)

None for required implementation.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The loop proceeds in fixed order but with conditional branching at each step:

1. Parse `query` using regex to extract `description` (everything before size/price keywords), `size` (pattern `size\s+\S+` or just a standalone size token like "M"), and `max_price` (pattern `under\s+\$?(\d+)`). Store in `session["parsed"]`.

2. Call `search_listings(description, size, max_price)`. Store result in `session["search_results"]`.
   - **Branch: empty results** → set `session["error"] = f"No listings found for '{description}' (size: {size}, max: ${max_price}). Try broader terms or a higher price."` → return session immediately. `suggest_outfit` and `create_fit_card` are NOT called.
   - **Branch: results found** → set `session["selected_item"] = session["search_results"][0]` → continue.

3. Call `suggest_outfit(session["selected_item"], session["wardrobe"])`. Store result in `session["outfit_suggestion"]`.
   - If the returned string starts with "Error", set `session["error"]` to it and return session early.
   - Otherwise continue.

4. Call `create_fit_card(session["outfit_suggestion"], session["selected_item"])`. Store result in `session["fit_card"]`.
   - If the returned string starts with "Error" or "Cannot", set `session["error"]` to it (but fit_card remains set, since the UI can display it as a message).

5. Return the completed session.

The agent never calls all three tools unconditionally — it halts at step 2 if search returns empty.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single `session` dict initialized in `_new_session()`. Keys:
- `query` (str): original user input
- `parsed` (dict): extracted `description`, `size`, `max_price`
- `search_results` (list[dict]): raw output of `search_listings`
- `selected_item` (dict|None): `search_results[0]` — the item passed to `suggest_outfit`
- `wardrobe` (dict): user's wardrobe, passed in at `run_agent()` call time
- `outfit_suggestion` (str|None): output of `suggest_outfit`, passed to `create_fit_card`
- `fit_card` (str|None): output of `create_fit_card`, displayed in the UI
- `error` (str|None): set on early termination; all downstream output fields remain None

Each tool receives only the specific session fields it needs (not the full dict), which makes each tool independently testable. State flows: `selected_item` is the bridge from tool 1→2; `outfit_suggestion` is the bridge from tool 2→3.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Sets `session["error"]` to "No listings found for '{description}' (size: {size}, max: ${max_price}). Try broader terms or a higher price." Returns session immediately. `suggest_outfit` and `create_fit_card` are not called. |
| suggest_outfit | Wardrobe is empty | Calls LLM with a prompt for general styling advice instead of wardrobe-specific combos. Returns a non-empty string — never crashes or returns "". |
| create_fit_card | Outfit input is missing or empty string | Returns the string "Cannot generate a fit card without an outfit suggestion." immediately without calling the LLM. |

---

## Architecture

```
User query
    │
    ▼
run_agent(query, wardrobe)
    │
    ├─ Step 1: Parse query ──────────────────────────────────────────────────┐
    │   regex extracts description, size, max_price                          │
    │   → session["parsed"]                                                  │
    │                                                                        │
    ├─ Step 2: search_listings(description, size, max_price)                 │
    │   │                                                                    │
    │   ├── results == []                                                    │
    │   │       │                                                            │
    │   │       └─► session["error"] = "No listings found..." ──► return ◄──┘
    │   │                                                          (error)
    │   └── results = [item, ...]
    │           │
    │           └─► session["search_results"] = results
    │               session["selected_item"] = results[0]
    │
    ├─ Step 3: suggest_outfit(selected_item, wardrobe)
    │   │
    │   ├── wardrobe["items"] == []
    │   │       └─► LLM: general styling advice for item
    │   │
    │   └── wardrobe["items"] = [...]
    │           └─► LLM: specific outfit combos using wardrobe pieces
    │
    │   → session["outfit_suggestion"] = LLM response string
    │
    ├─ Step 4: create_fit_card(outfit_suggestion, selected_item)
    │   │
    │   ├── outfit is empty/whitespace
    │   │       └─► return "Cannot generate a fit card..." string
    │   │
    │   └── outfit is valid
    │           └─► LLM (temp=1.2): casual OOTD caption
    │
    │   → session["fit_card"] = caption string
    │
    └─ Step 5: return session
                    │
                    ▼
            session dict returned to app.py handle_query()
            which maps fields → three Gradio output panels
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`: I'll give Claude the Tool 1 spec block (inputs, return value, failure mode) and ask it to implement the function using `load_listings()` from the data loader, scoring by keyword overlap across title/description/style_tags. I'll verify the generated code filters by both `max_price` and `size`, scores items, and returns `[]` on no matches. I'll test with 3 queries: a broad one (should return many), a size/price filtered one, and an impossible one (should return `[]`).

For `suggest_outfit`: I'll give Claude the Tool 2 spec block and the wardrobe schema structure. I'll ask it to generate a Groq llama-3.3-70b-versatile call that handles both the empty-wardrobe and populated-wardrobe paths. I'll verify the generated code branches on `wardrobe['items']` being empty, and test with both `get_empty_wardrobe()` and `get_example_wardrobe()`.

For `create_fit_card`: I'll give Claude the Tool 3 spec block (caption style guidelines, temperature requirement, guard on empty outfit). I'll verify the guard is present before any LLM call, and run 3 times on the same input to confirm output varies.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Architecture diagram and the Planning Loop + State Management sections verbatim. I'll ask it to implement `run_agent()` following the numbered TODOs in agent.py. Before using the code, I'll verify: (1) it branches on empty `search_results` before calling `suggest_outfit`, (2) it stores all values in the session dict, (3) it does not call all three tools unconditionally. I'll then run both CLI test cases in agent.py to confirm the happy path and no-results path behave correctly.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query. Regex extracts: `description = "vintage graphic tee"`, `size = None` (no size mentioned), `max_price = 30.0`. Stores in `session["parsed"]`. Calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`.

**Step 2:**
`search_listings` loads all listings, filters to those with `price <= 30.0`, scores each by keyword overlap ("vintage", "graphic", "tee") against title, description, style_tags, category, colors. Returns e.g. `[{"id": "lst_002", "title": "Y2K Baby Tee — Butterfly Print", "price": 18.0, "platform": "depop", ...}, ...]` sorted by score. Since results are non-empty, `session["selected_item"]` = the Y2K Baby Tee dict. Continues to Step 3.

**Step 3:**
Calls `suggest_outfit(selected_item=<Y2K Baby Tee dict>, wardrobe=<example_wardrobe>)`. The example wardrobe has items (baggy jeans, khaki trousers, etc.), so the LLM receives a prompt listing the wardrobe pieces and the new tee and returns: "Pair this Y2K baby tee with your baggy dark wash jeans and chunky white sneakers for a classic early 2000s street look. Alternatively, tuck it into your wide-leg khakis and add the black zip hoodie for a bit of edge." Stores in `session["outfit_suggestion"]`.

**Step 4:**
Calls `create_fit_card(outfit="Pair this Y2K baby tee...", new_item=<Y2K Baby Tee dict>)`. LLM generates: "found this $18 y2k butterfly tee on depop and it was absolutely made for my baggy jeans era 🦋 rolled the sleeves once and paired it with my chunky sneakers and i feel like it's 2003. sometimes the thrift gods just provide." Stores in `session["fit_card"]`.

**Final output to user:**
- Panel 1 (Top listing found): "Y2K Baby Tee — Butterfly Print | $18.00 | depop | Size: S/M | Condition: excellent | Tags: y2k, vintage, graphic tee, cottagecore"
- Panel 2 (Outfit idea): The full suggest_outfit string with specific wardrobe combos.
- Panel 3 (Your fit card): The casual caption string.
