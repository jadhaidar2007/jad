# jw_ainpc: AI NPCs for FiveM

NPCs that hold real conversations with your players. Powered by Claude (default) or any OpenAI-compatible model, including free local models through Ollama. Works on QBCore, Qbox, ESX and standalone servers, with ox_target, qb-target or a plain "press E" prompt.

## Install in 5 steps
1. Copy the `jw_ainpc` folder into your server's `resources/` directory. Do not rename it.
2. Get an API key at https://console.anthropic.com (or see CONFIG.md for OpenAI/Groq/OpenRouter/Ollama).
3. Add to `server.cfg` (use `set`, never `setr`, so players never receive it):
   ```
   set jw_ainpc_key "sk-ant-..."
   ensure jw_ainpc
   ```
4. Start the server. The console prints `[jw_ainpc] v1.0.0 started | bridge: ... | key: set`.
   Test without joining: type `ainpc test unicorn_bartender Any gossip tonight?` in the server console.
5. Join, walk up to Vinnie at the Vanilla Unicorn bar and talk. Then edit `config.lua` to add your own NPCs. Use `/ainpc_coords` in game to get positions.

## Requirements
- FiveM server artifact with OneSync (recommended, for the server-side distance check).
- Optional: ox_target or qb-target, oxmysql (only for cross-session memory).
- An API key for your chosen provider, or a local Ollama.

## Hooking actions
NPCs can trigger whitelisted actions (`discount`, `give_hint`, `call_cops` out of the box). Listen on the server:
```lua
AddEventHandler('jw_ainpc:action', function(src, npcId, action, arg)
    if action == 'discount' then -- arg is a validated number between your min and max
    end
end)
```
See `examples/` and CONFIG.md.

## Admin commands
`ainpc stats` · `ainpc list` · `ainpc test <npcId> <message>` · `ainpc reload` · `ainpc forget <identifier>` (needs ace `command.ainpc`; the server console is always allowed).

## Files you can edit
`config.lua`, `locales/`, `bridge/`, `examples/` stay open in the escrowed release.

## Developer notes (this repo)
```
cd ainpc_pack
luacheck jw_ainpc         # lint
busted                    # 80 unit tests
lua5.4 tools/boot_sim.lua # headless boot simulation (manifest + all scripts + commands)
node tools/nui_check.js   # headless NUI check (Playwright)
tools/package.sh          # runs all of the above, then builds dist/jw_ainpc_v<version>.zip
```
