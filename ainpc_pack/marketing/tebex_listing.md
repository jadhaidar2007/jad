# Tebex product page (draft, do not publish until tested in game)

**Title:** AI NPCs: Real Conversations (Claude / OpenAI / Ollama) | QBCore · Qbox · ESX · Standalone

**Hook:** Your players walk up to the bartender, type anything, and he answers in character, remembers them, and can hand out discounts or call the cops.

## Description
Static NPCs with three canned lines are the most immersion-breaking thing in any city. jw_ainpc lets you place NPCs that actually talk. Each one has a personality, knows your server's lore, sees who is talking to them (RP name, job, how wealthy they look), knows the time and weather, and remembers the last conversation.

Everything runs on **your** server with **your** API key. There is no middleman service, no subscription to us, and no player data passing through anyone else's backend. Pick Claude, OpenAI, Groq, OpenRouter, or a free local model with Ollama.

NPCs can also **do** things: give a haggling player a discount, slip a trusted player a quest hint, or call the police on someone who threatens them. The AI can only request actions you whitelisted. The server validates every argument and fires a normal server event you hook into. It can never give money or run code.

## Features
- Free-form AI conversations, in character, in any language (UI ships in English, Arabic (RTL), German, Spanish and French)
- Per-player memory per NPC, with optional cross-restart memory through oxmysql (table created automatically)
- Player context: RP name, job and wealth bracket from QBCore / Qbox / ESX, plus in-game time and weather
- Whitelisted actions (`[ACTION:discount:15]`): validated, clamped, at most one per reply, exposed as `jw_ainpc:action`
- Cost controls: per-player cooldown, daily caps, server-wide per-minute and per-day ceilings, live `ainpc stats`
- Abuse filter and prompt-injection guard; API failures produce an in-character line, never an error
- Auto-detects ox_target / qb-target / E prompt and QBCore / Qbox / ESX / standalone
- 5 ready NPCs: Vanilla Unicorn bartender, Pillbox nurse, Legion Square informant, Mission Row desk officer, Ammu-Nation clerk
- Test from the server console without a game client: `ainpc test unicorn_bartender hello`
- Clean dark chat UI with typing indicator; no build step
- Open config, locales, framework bridge and example hooks

## Requirements
- FiveM server (OneSync recommended)
- An API key (Anthropic, OpenAI, Groq or OpenRouter) **or** Ollama running locally
- Optional: ox_target or qb-target, oxmysql

## Install
1. Drop `jw_ainpc` in `resources/` (keep the folder name)
2. `set jw_ainpc_key "your-key"` in server.cfg
3. `ensure jw_ainpc`
4. Restart, then run `ainpc test unicorn_bartender hello` in the console
5. Walk up to an NPC and talk. Add your own in config.lua

## FAQ
**How much does the AI cost?** You pay your AI provider directly. With the default Claude Haiku 5.5 model, a typical message costs roughly $0.0002 (about $2 per 10,000 messages; estimate from Anthropic's published per-token prices, check `ainpc stats` on your server). The default server-wide cap of 3,000 messages a day bounds the worst case at well under $1/day, and you can set it lower. With Ollama it is free but needs a GPU.

**Does it work with QBCore / Qbox / ESX?** Yes, auto-detected. Standalone also works (uses the FiveM player name).

**Can players break it?** They can try. NPCs are instructed to stay in character and never reveal instructions, but no AI is 100% jailbreak-proof, so the design does not rely on it. The AI cannot touch your economy: actions are whitelisted, argument-validated and capped by you, and the worst a jailbreak can produce is an odd line of dialogue. Abusive messages are filtered locally and cost nothing, and caps stop spam.

**Is my API key safe?** It is a server convar set with `set`, used only server-side, and never sent to players.

**Do players need anything?** No. It is a normal resource.

**Voice?** Text only in 1.0. Voice is on the roadmap.

**Is it escrowed?** The core is escrowed. config.lua, locales, framework bridge, example hooks and the UI stay open.
