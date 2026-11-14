# Architecture

```
player types in NUI ──► client/nui.lua ──TriggerServerEvent('jw_ainpc:ask', npcId, msg, {hour, weather})──►
server/main.lua  (validates types, NPC exists, player within ServerDistanceCheck, builds context via bridge)
   └─► server/core.lua  Core:ask()
         1. sanitize + length cap            (shared/init.lua Util)
         2. abuse filter (local, no tokens)
         3. in-flight guard, rate limits     (server/ratelimit.lua)
         4. API key from convar              (Core.readApiKey)
         5. memory load (oxmysql, optional)  (server/persistence.lua)
         6. prompt = persona + lore + player ctx + world + guard rules + allowed actions + history
                                             (server/prompt.lua)
         7. provider request/parse           (server/providers/anthropic.lua | openai_compat.lua)
            with our own timeout timer
         8. parse reply: strip [ACTION:..], whitelist + validate args, cap length (server/parser.lua)
         9. memory append (+ DB save)        (server/memory.lua)
        10. fire TriggerEvent('jw_ainpc:action', src, npcId, name, arg) for valid actions
   ◄── TriggerClientEvent('jw_ainpc:reply', src, npcId, text)
```

## Rules
- **Every API call is server-side.** The key lives in the convar `jw_ainpc_key` set with `set` (not replicated). It is never in config.lua and never sent to clients.
- **Core has zero natives.** All FiveM functions are injected (`http`, `setTimeout`, `log`, `onAction`, `persistence`, `clock`), which is why the whole pipeline is unit-tested headlessly.
- **One global namespace** `AINPC` (plus FiveM's conventional `Config`). luacheck enforces no other globals.
- **Players never see errors.** Every failure path calls `reply()` exactly once with an in-character fallback line from `Config.Fallbacks`.
- **The model cannot affect the game except through whitelisted actions.** It can only print a tag; the server decides.

## Modules
| File | Side | Purpose |
|---|---|---|
| shared/init.lua | both | namespace, version, sanitize/utf8-safe cut/truncate/blocked words/money bracket |
| shared/locale.lua, locales/*.lua | both | UI strings (en, ar with RTL, de, es, fr) |
| config.lua | both | all owner settings (escrow-ignored) |
| client/main.lua | client | ped streaming (spawn < SpawnDistance, despawn beyond, not while talking), invincible/frozen/no-flee, blips, ox_target / qb-target / E prompt |
| client/nui.lua | client | open/close, focus, sends message + world context, auto-close when walking away or dead |
| html/* | NUI | dark chat panel, typing indicator, per-NPC session history, ESC close, textContent only (no HTML injection), 20 s input unlock safety |
| server/ratelimit.lua | server | cooldown, per-player daily, global per-minute, global per-day |
| server/memory.lua | server | last N exchanges per player per NPC; always starts on a user turn |
| server/prompt.lua | server | system prompt incl. injection guard |
| server/parser.lua | server | action tags, validation, name-prefix strip, length cap |
| server/providers/*.lua | server | request/response shapes |
| server/core.lua | server | pipeline, stats, timeouts |
| server/persistence.lua | server | oxmysql table auto-create, load/save/forget |
| bridge/*.lua | server | standalone / qb / qbx / esx context + identifier; auto-detect (Qbox before QBCore) |
| server/main.lua | server | net events, distance check, admin commands |
| examples/*.lua | server | discount, quest hint, call cops hooks |

## Admin commands (ace `command.ainpc`, console always allowed)
`ainpc stats`, `ainpc list`, `ainpc test <npcId> <message>`, `ainpc reload`, `ainpc forget <identifier>`. Client: `/ainpc_coords` prints your position as a vector4.
