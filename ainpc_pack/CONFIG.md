# Configuration reference (`config.lua`)

| Option | Default | Meaning |
|---|---|---|
| `Debug` | `false` | Extra console logs (`debug` level). |
| `Locale` | `'en'` | UI language: `en`, `ar` (right-to-left), `de`, `es`, `fr`. NPC reply language is per NPC. |
| `Framework` | `'auto'` | `auto` detects `qbx_core`, then `qb-core`, then `es_extended`, else standalone. Force with `qb`, `qbx`, `esx`, `standalone`. |
| `Interaction` | `'auto'` | `auto` uses ox_target, then qb-target, else the E prompt. Force with `ox_target`, `qb-target`, `prompt`. |
| `Provider.type` | `'anthropic'` | `anthropic` (Claude Messages API) or `openai_compat` (OpenAI, Groq, OpenRouter, Ollama, LM Studio...). |
| `Provider.model` | `'claude-haiku-5-5'` | Model id. Haiku is the fast, cheap choice for chat. |
| `Provider.maxTokens` | `400` | Max tokens per reply, including any model "thinking". Reply length is controlled by `MaxReplyChars`. |
| `Provider.effort` | `'low'` | Anthropic only: `low`, `medium`, `high`, or `false` to omit. Low is fastest and cheapest. |
| `Provider.temperature` | unset | openai_compat only. Never sent to Claude (current Claude models reject it). |
| `Provider.url` | provider default | Endpoint. Required for non-OpenAI openai_compat targets; examples are in config.lua. |
| `Provider.apiVersion` | `'2026-10-21'` | Anthropic `anthropic-version` header. |
| `ApiKeyConvar` | `'jw_ainpc_key'` | Name of the server convar holding the key. Placeholders like `your-key` count as missing. Not needed for keyless local servers. |
| `RequestTimeoutSeconds` | `15` | After this, the NPC answers with a fallback line. |
| `DefaultLanguage` | `'English'` | Reply language when an NPC has no `language`. |
| `MaxReplyChars` | `300` | Hard cap on reply length (cut on a word boundary). |
| `MemoryExchanges` | `6` | Question/answer pairs remembered per player per NPC. More memory = more input tokens per message. |
| `Persistence.enabled` | `false` | Remember players across restarts with oxmysql. Table auto-created (`sql/jw_ainpc.sql` for reference). |
| `Persistence.table` | `'jw_ainpc_memory'` | Table name (letters, digits, `_`). |
| `Limits.cooldownSeconds` | `4` | Minimum seconds between one player's messages. |
| `Limits.dailyPerPlayer` | `80` | Messages per player per day. `0` = unlimited. |
| `Limits.globalPerMinute` | `40` | All players combined, per rolling minute. |
| `Limits.globalPerDay` | `3000` | Server-wide daily ceiling: your worst-case bill. `0` = unlimited. |
| `Limits.maxInputChars` | `200` | Player message length cap (client and server). |
| `ProfanityFilter` / `BlockedWords` | `true` / list | Whole-word match. Blocked messages get the `abuse` fallback and cost nothing. |
| `SpawnDistance` | `100.0` | Peds spawn within this distance and despawn beyond it. |
| `InteractDistance` | `2.5` | Target/prompt range. The chat closes if you walk 3 m beyond it. |
| `ServerDistanceCheck` | `6.0` | Server ignores messages from players further than this (OneSync). `0` disables it. |
| `Fallbacks` | lines | In-character lines for `error`, `cooldown`, `limit`, `busy`, `abuse`, `empty`. NPCs can override with their own `fallbacks` table. |
| `ServerLore` | 2 lines | Facts every NPC knows. Each line costs tokens on every message, so keep it short. |
| `Actions` | 3 actions | Whitelist (see below). |
| `NPCs` | 5 examples | See below. |

## NPC fields
| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique id, used in commands, events and memory. |
| `name` | yes | What the NPC is called (also stripped if the model prefixes it). |
| `role` | yes | One line: "the bartender at...". |
| `model` | yes | Ped model name. |
| `coords` | yes | `vector4(x, y, z, heading)`. The 5 examples are marked TODO: verify them in game (MLOs move interiors). |
| `scenario` | no | e.g. `WORLD_HUMAN_SMOKING`. |
| `persona` | yes | Personality, speech style, what they will and won't do. |
| `knowledge` | no | Lore lines only this NPC knows. |
| `language` | no | Reply language, e.g. `'Arabic'`. |
| `maxReplyChars` | no | Per-NPC override. |
| `actions` | no | Names from `Config.Actions` this NPC may trigger. |
| `fallbacks` | no | Per-NPC fallback lines, same keys as `Config.Fallbacks`. |
| `blip` | no | `true` or `{ sprite = 280 }`. |

## Actions
```lua
Config.Actions = {
    discount  = { type = 'number', min = 5, max = 20, description = 'when to use it' },
    give_hint = { type = 'enum', values = { 'heist_1', 'drugs_1' }, description = '...' },
    call_cops = { type = 'none', description = '...' },
}
```
The model ends its reply with `[ACTION:discount:15]`. The server removes the tag, checks that the NPC is allowed to use the action, validates the argument (numbers are clamped, enum values must match exactly), fires at most one action per reply, and then triggers:
```lua
TriggerEvent('jw_ainpc:action', playerSrc, npcId, actionName, arg)          -- server
TriggerClientEvent('jw_ainpc:actionFired', playerSrc, npcId, actionName, arg) -- that player's client
```
For hints, the model only picks **which** hint id; the text lives in `examples/quest_hint.lua`, so the AI cannot leak anything you did not write.

## Provider examples
```lua
-- Groq
Config.Provider = { type = 'openai_compat', url = 'https://api.groq.com/openai/v1/chat/completions', model = 'llama-3.1-8b-instant', maxTokens = 200 }
-- Local Ollama (no key, no cost; needs a decent GPU on the same machine)
Config.Provider = { type = 'openai_compat', url = 'http://127.0.0.1:11434/v1/chat/completions', model = 'llama3.1', maxTokens = 200 }
```
