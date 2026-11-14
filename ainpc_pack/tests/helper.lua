-- Loads resource files into a fresh environment with mocked FiveM globals.
local H = {}
local ROOT = 'jw_ainpc/'

H.json = require('dkjson')

function H.vector4(x, y, z, w) return { x = x, y = y, z = z, w = w } end

function H.reset()
    _G.AINPC = nil
    _G.Config = nil
    _G.vector4 = H.vector4
    _G.json = { encode = function(t) return H.json.encode(t) end, decode = function(s) return H.json.decode(s) end }
    _G.GetResourceState = function() return 'missing' end
    _G.GetPlayerName = function(src) return 'Player' .. tostring(src) end
    _G.GetPlayerIdentifierByType = function(src) return 'license:abc' .. tostring(src) end
    for _, f in ipairs({
        'shared/init.lua', 'shared/locale.lua', 'locales/en.lua', 'locales/ar.lua', 'locales/de.lua',
        'locales/es.lua', 'locales/fr.lua', 'config.lua',
        'server/ratelimit.lua', 'server/memory.lua', 'server/parser.lua', 'server/prompt.lua',
        'server/providers/anthropic.lua', 'server/providers/openai_compat.lua', 'server/core.lua',
        'bridge/standalone.lua', 'bridge/qb.lua', 'bridge/qbx.lua', 'bridge/esx.lua', 'bridge/init.lua',
    }) do
        dofile(ROOT .. f)
    end
end

-- A controllable clock for rate limiting.
function H.clock(start, day)
    local c = { t = start or 1000, d = day or '2026-11-14' }
    c.now = function() return c.t end
    c.day = function() return c.d end
    return c
end

-- Fake HTTP: records requests; responds synchronously with a canned body unless deferred.
function H.fakeHttp(responder)
    local calls = {}
    local fn = function(url, method, body, headers, cb)
        local call = { url = url, method = method, body = body, headers = headers, cb = cb }
        calls[#calls + 1] = call
        if responder then
            local status, resp = responder(call)
            if status then cb(status, resp) end
        end
    end
    return fn, calls
end

function H.anthropicOk(text, inTok, outTok)
    return 200, H.json.encode({
        content = { { type = 'text', text = text } },
        usage = { input_tokens = inTok or 100, output_tokens = outTok or 20 },
    })
end

function H.newCore(opts)
    opts = opts or {}
    local http, calls = H.fakeHttp(opts.responder or function() return H.anthropicOk('Hey pal.') end)
    local actions, logs = {}, {}
    local core = AINPC.Core.new({
        config = opts.config or Config,
        json = _G.json,
        getApiKey = function() return opts.key == nil and 'test-key' or opts.key end,
        http = http,
        setTimeout = opts.setTimeout,
        log = function(level, msg) logs[#logs + 1] = { level = level, msg = msg } end,
        onAction = function(src, npcId, name, arg) actions[#actions + 1] = { src = src, npc = npcId, name = name, arg = arg } end,
        persistence = opts.persistence,
        clock = opts.clock or H.clock(),
    })
    return core, calls, actions, logs
end

function H.ask(core, npcId, message, extra)
    local result = {}
    local req = { src = 1, identifier = 'license:p1', npcId = npcId, message = message, ctx = {} }
    for k, v in pairs(extra or {}) do req[k] = v end
    req.reply = function(text, meta) result.text = text; result.meta = meta or {}; result.calls = (result.calls or 0) + 1 end
    core:ask(req)
    return result
end

return H
