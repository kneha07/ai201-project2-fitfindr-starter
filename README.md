# FitFindr

I built this for the agent project — it's a tool that helps you find secondhand clothes and figure out how to actually wear them. You type in what you're looking for, it searches a mock thrift dataset, suggests an outfit using stuff you already own, and spits out a little caption you could use for a post.

---

## Setup

```bash
git clone <your-fork-url>
cd fitfindr
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You'll need a Groq API key (free at console.groq.com — same one from project 1). Make a `.env` file in the root:

```
GROQ_API_KEY=your_key_here
```

Then just run `python app.py` and open the localhost URL it gives you.

---

## The Three Tools

### `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`

Searches through the mock listings data. First it filters by price and size if you gave those, then it scores whatever's left by how many of your keywords show up in the title, description, style_tags, category, colors, and brand. Returns a sorted list — best match first. If nothing matches, it just returns `[]`, no exceptions.

Each item in the list has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.

### `suggest_outfit(new_item: dict, wardrobe: dict) → str`

Takes the item you found and your wardrobe, sends both to the LLM, and asks it to come up with 1-2 outfit combos. If you have stuff in your wardrobe it names specific pieces; if the wardrobe is empty it just gives general advice about what would work with the item. Always returns a string.

### `create_fit_card(outfit: str, new_item: dict) → str`

Turns the outfit suggestion into something you'd actually caption a photo with. 2-4 sentences, mentions the item name, price, and where it's from. Uses a higher temperature so it doesn't sound the same every time. If you pass an empty outfit string it returns an error message instead of calling the LLM.

---

## How the Planning Loop Works

`run_agent()` in agent.py goes through four steps, but it's not a fixed sequence — it bails early if something doesn't work out.

1. **Parse the query** — regex pulls out the item description, size (looks for "size M" or standalone tokens like "XL", "W28"), and a price limit ("under $30"). Everything else becomes the description after stripping filler phrases.

2. **Search listings** — calls `search_listings()` with what it parsed. If results come back empty, it sets an error message in the session and returns right there. `suggest_outfit` and `create_fit_card` never get called with empty input.

3. **Suggest outfit** — calls `suggest_outfit()` with the top search result and your wardrobe. If the LLM comes back with an error it bails here too.

4. **Create fit card** — calls `create_fit_card()` with the outfit and the item. Returns the finished session.

The key thing is step 2 — if search finds nothing, the other two tools don't run at all.

---

## State Management

Everything lives in a session dict that gets passed around. The tools don't share global state — each one just receives the specific fields it needs.

| Field | Written when | Used by |
|---|---|---|
| `query` | start | parsing |
| `parsed` | after parsing | `search_listings` |
| `search_results` | after tool 1 | picking selected_item |
| `selected_item` | after non-empty results | tools 2 and 3 |
| `wardrobe` | start (passed in) | `suggest_outfit` |
| `outfit_suggestion` | after tool 2 | `create_fit_card` |
| `fit_card` | after tool 3 | UI |
| `error` | on early exit | UI |

`selected_item` is how tool 1's result gets to tool 2 without the user retyping anything. `outfit_suggestion` does the same thing between tools 2 and 3.

---

## Error Handling

| Tool | What breaks | What happens |
|---|---|---|
| `search_listings` | No listings match | Sets `session["error"]` to something like "No listings found for 'designer ballgown' (size: XXS, max: $5). Try broader search terms, remove the size filter, or raise your price limit." Returns immediately — tools 2 and 3 don't run. |
| `suggest_outfit` | Wardrobe is empty | Doesn't crash — prompts the LLM for general styling advice instead. Returns a non-empty string either way. |
| `create_fit_card` | `outfit` is empty or blank | Returns "Cannot generate a fit card without an outfit suggestion." without touching the LLM. |

I actually tested these by running them directly:

```bash
python3 -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
# returns []

python3 -c "from tools import create_fit_card, search_listings; r = search_listings('tee', None, 50); print(create_fit_card('', r[0]))"
# returns "Cannot generate a fit card without an outfit suggestion."
```

---

## Spec Reflection

Writing out the planning loop in planning.md before touching the code was actually useful — it made clear that `suggest_outfit` can never receive `None` as its first argument, which forced me to put the early-return check right after search results come back rather than hoping it wouldn't happen.

One thing that changed from the spec: I originally planned to parse size with just a `"size M"` pattern. The actual listings use sizes like `"S/M"`, `"XL (oversized)"`, and `"W30 L30"`, so I had to add a second regex pass for standalone tokens. The spec only described the first pattern.

---

## AI Usage

**search_listings:** I gave Claude the Tool 1 spec block from planning.md — inputs, return value, the failure mode, and the instruction to use `load_listings()`. The code it generated only scored against title and style_tags. I overrode that to also include description and colors, because otherwise queries like "rust corduroy" or "black boots" didn't surface the right results.

**run_agent() planning loop:** I gave Claude the architecture diagram from planning.md and asked it to implement `run_agent()` following the TODO steps in agent.py. The generated version put the empty-results branch after `selected_item` was already assigned, which would have let a `None` slip through if the branch condition ever misfired. I moved the check to right after `search_results` is set, before `selected_item` gets touched — matching what the spec actually described.
