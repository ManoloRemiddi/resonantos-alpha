# Chatbot Page — Browser Audit Results (2026-02-21)

## Critical Bugs

### BUG-1: Conversations tab completely broken
- **Symptom:** "Error loading conversations — Unexpected token '<', "
- **Root cause:** JS fetches `/api/conversations?limit=...&offset=...` (line 931 in chatbots.html) but server only defines `/api/chatbots/<bot_id>/conversations` (line 3798 in server_v2.py). The missing route returns HTML 404, which JS tries to parse as JSON.
- **Fix needed:** Either add `/api/conversations` route to server (aggregates across all bots) or fix JS to use the per-bot endpoint.

### BUG-2: Save button missing/invisible on most tabs
- **Symptom:** After editing Settings, Appearance, or Knowledge — there is NO visible Save button. The only save button ("💾 Save & Update") lives inside a `deploy-actions` container that is only visible on the Deploy tab, and even there it renders with height=0.
- **Root cause:** Save button is inside Deploy tab panel, hidden when other sub-tabs are active. CSS `display:none` or `height:0` on the parent.
- **Fix needed:** Save button must be persistently visible across all sub-tabs (Settings, Appearance, Knowledge, Deploy), or each tab needs its own save. This is the #1 UX problem — users make changes they can never save.

### BUG-3: Edit button requires double-click
- **Symptom:** First click on "Edit" shows the sub-tabs (Settings/Appearance/Knowledge/Deploy) but content area is EMPTY. Second click on "⚙️ Settings" tab loads the form.
- **Root cause:** The `editBot()` function switches to edit mode and shows sub-tabs, but doesn't auto-select/render the first tab panel.
- **Fix needed:** `editBot()` should auto-trigger the Settings tab content load.

### BUG-4: Knowledge tab — "Error loading files"
- **Symptom:** Red "Error loading files" message in the uploaded files section.
- **Root cause:** Likely fetching from a non-existent API endpoint for knowledge base files.
- **Fix needed:** Check the fetch URL and add the server route if missing.

### BUG-5: "Could not load system keys" warning
- **Symptom:** Large ⚠️ warning on Settings tab saying "Could not load system keys".
- **Root cause:** The system keys API endpoint returns an error. Likely trying to read OpenClaw config but the path or permissions are wrong.
- **Fix needed:** Either fix the API endpoint or gracefully handle the case (don't show a scary warning).

## UX Issues

### UX-1: No Back/Cancel button in edit mode
- Once you click Edit, there's no way to go back to the chatbot list except clicking "My Chatbots" tab. No Cancel button, no breadcrumb.

### UX-2: No navigation breadcrumbs
- When editing a chatbot, the page title still says "Chatbot Manager" with no indication of WHICH chatbot you're editing.

### UX-3: Create flow goes straight to Settings
- Clicking "Create New Chatbot" instantly creates a bot and opens edit mode. There's no wizard/confirmation step. The bot is named "My Chatbot" by default.

### UX-4: Analytics tab — empty state OK but no clear CTA
- Shows "Analytics data will appear here once chatbots are active" — acceptable for now.

### UX-5: Addons tab functional
- Displays pricing cards with SOL/USDT/USDC payment options. Looks complete.

## Files to Modify

1. **`templates/chatbots.html`** (3611 lines) — All JS is inline. Main file for fixes.
2. **`server_v2.py`** — API routes (add `/api/conversations`, fix knowledge base files endpoint).

## Backup Location
`$RESONANTOS_HOME/dashboard/backups/chatbots-20260221-081906/`

## Priority Order
1. BUG-2 (Save button) — Users literally cannot save edits. Showstopper.
2. BUG-3 (Edit double-click) — Confusing first impression.
3. BUG-1 (Conversations broken) — Entire tab non-functional.
4. BUG-4 (Knowledge files) — Feature broken.
5. BUG-5 (System keys warning) — Scary but cosmetic.
6. UX-1/UX-2 (Back button + breadcrumbs) — Polish.
