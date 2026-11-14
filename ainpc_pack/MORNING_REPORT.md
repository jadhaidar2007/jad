# Morning report: jw_ainpc (AI NPC Pack)

Everything is in `ainpc_pack/` on branch `claude/happy-johnson-bqffoz`. Nothing was published, purchased or posted.

## Done
- **Resource** `jw_ainpc/`: fxmanifest, config with 5 NPCs, client (ped streaming, ox_target / qb-target / E prompt, blips), NUI chat, server pipeline (prompt builder, Claude + OpenAI-compatible providers, parser, memory, rate limits, timeouts, fallbacks), QBCore/Qbox/ESX/standalone bridges, optional oxmysql memory, whitelisted actions + 3 example hooks, admin commands, 5 UI languages.
- **Quality**: `luacheck` 0 warnings; `busted` **80/80 passing**; headless boot simulation passes; headless browser check of the chat UI passes (including an HTML-injection test).
- **Package**: `dist/jw_ainpc_v1.0.0.zip` (43 files, resource only). `tools/package.sh` rebuilds it and refuses if lint, tests, the simulation or a key scan fails.
- **Docs**: README (5-step install), CONFIG, CHANGELOG, LICENSE, ARCHITECTURE, RESEARCH (competitors with links), DECISIONS.
- **Marketing**: Tebex page + FAQ, pricing proposal, 60 s shot list, 5 post drafts, 20 verified buyer channels, UI screenshot (`marketing/nui_preview.png`).

## Things you should know (read these)
1. **Real competition exists.** Intel NPC / nCore NPC PRO launched in June at €30.75 and is now €55-60. It is much bigger than ours (ambient peds, trust, gossip). We win on simplicity, owning your own key/provider (incl. free Ollama), safe actions and cost caps, not on breadth. The "€5k/month" claim in the original post is still unverified, and the market is not empty.
2. **Tebex takes 15%** on FiveM sales (5% elsewhere).
3. **I changed two things from your plan** (details in DECISIONS #17-18): the license is per Cfx account, because escrow can't enforce "single-server"; and pricing splits escrow vs open source rather than putting persistence in its own tier.
4. **r/FiveM bans paid promotion.** Don't post the drafts there.
5. I found 20 verified buyer channels, not 30. I didn't pad the list.
6. A bug I nearly shipped: Claude's current models reject `temperature` (HTTP 400). Fixed, and covered by a test.

## Not tested (needs you)
- **No real FXServer boot**: the sandbox's proxy blocked runtime.fivem.net. The simulator covers manifest/script-load/command errors, but **not** real native behaviour.
- **No game client**: ped spawning, scenarios, targeting, NUI focus/ESC in game, and the server distance check with real OneSync coordinates.
- **No live AI call**: no `ANTHROPIC_API_KEY` was on the machine. Request/response shapes are tested against documented formats only. `lua5.4 tools/boot_sim.lua --live` makes up to 3 real calls once a key is exported.
- **Coordinates**: all 5 are marked TODO (vanilla positions; MLOs change them).
- **Persistence and the framework bridges**: tested with mocks only; never against real oxmysql / QBCore / ESX.
- Known small issue: on QBCore/ESX, if the framework unloads the player before `playerDropped`, that player's RAM memory isn't freed until restart (a few KB). Fine for 1.0; worth fixing later.
- Phase 2 (voice, NPC gossip, jobs scaffold): not started.

## HUMAN steps, in order (~1.5-2 h)
1. **Quick check (5 min, no game):** `cd ainpc_pack && export ANTHROPIC_API_KEY=sk-ant-... && lua5.4 tools/boot_sim.lua --live`. You should see Vinnie answer for real (max 3 calls, under $0.01).
2. **Test server (30 min):** create a Cfx.re account and a license key at https://portal.cfx.re, install FXServer + txAdmin, copy `jw_ainpc` into resources, add `set jw_ainpc_key "..."` and `ensure jw_ainpc` to server.cfg. Watch the console for the `started` line and any red errors.
3. **In game (30 min):** at each NPC run `/ainpc_coords` and fix coords in config.lua. Talk to all 5. Try: memory ("my name is..." then "remember me?"), haggling at Ammu-Nation (discount), a threat (call_cops in the console), walking away mid-chat, spam (cooldown), and a jailbreak attempt. Note anything odd for me with the exact message and the console output.
4. If possible, test once with qb-core or ESX and ox_target.
5. **Record the demo** from `marketing/demo_shotlist.md`. Use real replies only.
6. **Decide the price** (`marketing/pricing.md`).
7. **Tebex:** open a creator account, upload the zip at portal.cfx.re (Create asset), create a Tebex package linked to the asset, and paste `marketing/tebex_listing.md`.
8. **Post** the clip using the drafts and channels in `marketing/`, following each channel's rules.
