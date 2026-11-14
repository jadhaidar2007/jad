# Decisions log

| # | Decision | Why |
|---|---|---|
| 1 | Everything lives in `ainpc_pack/`, not the repo root. | The repo already holds an unrelated project (clipengine) with its own README. Overwriting it would destroy work. |
| 2 | Lua tooling: Lua 5.4 from apt; busted's deps `lua-term` and `mediator_lua` built from their git repos. | The network proxy blocks luarocks.org downloads. Everything else installed normally. |
| 3 | **No real FXServer boot.** Replaced with `tools/boot_sim.lua`. | The network proxy refuses runtime.fivem.net (HTTP 403 on CONNECT). I did not request a network change because that needs an approval prompt and Jad was asleep. The simulator parses fxmanifest, resolves every glob, loads all shared+server scripts in manifest order with stubbed natives, runs `ainpc stats/list/test/reload`, simulates the net event (near and far player), then loads all client scripts and runs a streaming tick plus an NUI open/send/close cycle. **It found a real bug** (`ainpc reload` ran config.lua in the wrong environment), now fixed. It cannot catch wrong native signatures or in-game behaviour; that is HUMAN step 2. |
| 4 | Default model `claude-haiku-5-5`, `anthropic-version: 2026-10-21`, `output_config.effort = "low"`, no `temperature`. | Checked against the current Claude API reference: Haiku 5.5 costs $0.10/$0.50 per MTok; current models return **HTTP 400** on non-default temperature; Haiku 5.5 thinks by default and thinking eats `max_tokens`, so we use low effort and allow 400 tokens. My first draft sent `temperature = 0.8`, which would have failed every request. |
| 5 | `Core` has no natives; everything is injected. | Makes the whole pipeline testable headlessly (80 tests). |
| 6 | One global `AINPC` + FiveM-conventional `Config`. | The plan says no global leaks; luacheck enforces only these two. |
| 7 | Actions: at most 1 per reply, numbers clamped, enums exact, NPC must list the action. The hint text lives in Lua, not in the prompt. | The model must never be able to create value or leak content you didn't write. |
| 8 | Abuse filter runs locally before any API call. | Saves tokens; spammers can't drain the budget. |
| 9 | In-flight guard self-expires after timeout + 15 s. | If an oxmysql callback never returns, the player would otherwise be locked out until restart. |
| 10 | Memory always starts on a `user` turn after trimming. | The Anthropic API rejects conversations whose first message is from the assistant. |
| 11 | Name-prefix stripping only strips the NPC's own name. | A generic "Word:" strip would eat legitimate replies like "Listen: the cops are coming." |
| 12 | Added `Limits.globalPerDay` (default 3,000). | Not in the plan, but it is the one setting that bounds an owner's worst-case bill; buyers will ask. |
| 13 | Server-side distance check (`ServerDistanceCheck`) on every message; skipped when OneSync is off. | Stops modded clients from talking to any NPC from anywhere. |
| 14 | `ainpc` command registered restricted (ace `command.ainpc`). | `test` spends API credit; only admins should run it. |
| 15 | Example hooks ignore src 0 (console). | `ainpc test` fires actions; without this they tried to send chat messages to the console. |
| 16 | Coordinates for the 5 NPCs are marked `TODO verify`. | They come from commonly published vanilla positions. MLOs (Pillbox, MRPD) move interiors, and I can't check in game. `/ainpc_coords` makes fixing them a 1-minute job. |
| 17 | **License = per purchasing Cfx account, not "single-server".** | Disagreement with the plan: escrow binds an asset to the buyer's account and runs on any server that account owns. A single-server clause can't be enforced, and the competitor offers all-servers-per-customer. |
| 18 | **Pricing tiers split on escrow vs open source, not on persistence.** | Disagreement with the plan: see marketing/pricing.md. |
| 19 | Outreach list has 20 verified channels, not 30. | I would not invent unverified links. r/FiveM bans paid promotion, which is flagged. |
| 20 | `lua54 'yes'` kept although deprecated. | The Cfx escrow FAQ still lists it as required; it is harmless. |
| 21 | NUI renders replies with `textContent` only; headless Playwright check injects `<img onerror>` to prove it. | Model output is untrusted. |
| 22 | Phase 2 backlog (voice, gossip, jobs scaffold) not started. | I prioritised correctness, tests and an honest kit over breadth. See MORNING_REPORT. |
