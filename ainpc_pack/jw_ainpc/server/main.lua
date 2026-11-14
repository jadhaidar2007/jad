-- FiveM glue: wires natives into the Core pipeline, handles net events and admin commands.
local RES = GetCurrentResourceName()

local function log(level, msg)
    if level == 'debug' and not Config.Debug then return end
    local colors = { error = '^1', warn = '^3', info = '^5', debug = '^7' }
    print(('%s[jw_ainpc] [%s]^7 %s'):format(colors[level] or '^7', level, msg))
end

local function getApiKey()
    return AINPC.Core.readApiKey(GetConvar, Config.ApiKeyConvar)
end

local function http(url, method, body, headers, cb)
    PerformHttpRequest(url, function(status, respBody)
        cb(status, respBody)
    end, method, body, headers)
end

local bridge = AINPC.detectBridge(Config.Framework)
local persistence = Config.Persistence and Config.Persistence.enabled
    and AINPC.Persistence.create(Config.Persistence, json, log) or nil

local core = AINPC.Core.new({
    config = Config,
    json = json,
    getApiKey = getApiKey,
    http = http,
    setTimeout = SetTimeout,
    log = log,
    persistence = persistence,
    onAction = function(src, npcId, name, arg)
        TriggerEvent('jw_ainpc:action', src, npcId, name, arg)
        if src and src > 0 then TriggerClientEvent('jw_ainpc:actionFired', src, npcId, name, arg) end
    end,
})
AINPC.core = core

local WEATHERS = {
    clear = true, extrasunny = true, clouds = true, overcast = true, rain = true, clearing = true,
    thunder = true, smog = true, foggy = true, xmas = true, snow = true, snowlight = true, blizzard = true,
    halloween = true, neutral = true,
}

local BRACKETS = {
    { below = 1000, label = 'broke' },
    { below = 20000, label = 'modestly off' },
    { below = 250000, label = 'comfortable', final = 'wealthy' },
}

local function buildContext(src, clientCtx)
    local ctx = bridge.getContext(src) or {}
    if ctx.moneyAmount then
        ctx.money = AINPC.Util.moneyBracket(ctx.moneyAmount, BRACKETS)
        ctx.moneyAmount = nil
    end
    if type(clientCtx) == 'table' then
        local hour = tonumber(clientCtx.hour)
        if hour and hour >= 0 and hour <= 23 then ctx.hour = math.floor(hour) end
        local weather = type(clientCtx.weather) == 'string' and clientCtx.weather:lower() or nil
        if weather and WEATHERS[weather] then ctx.weather = weather end
    end
    if ctx.playerName then ctx.playerName = AINPC.Util.sanitize(ctx.playerName, 40) end
    return ctx
end

local function nearNpc(src, npc)
    local maxDist = Config.ServerDistanceCheck
    if not maxDist or maxDist <= 0 then return true end
    local ped = GetPlayerPed(src)
    if not ped or ped == 0 then return true end -- OneSync off: can't check server-side
    local p = GetEntityCoords(ped)
    if p.x == 0.0 and p.y == 0.0 and p.z == 0.0 then return true end
    local c = npc.coords
    local dx, dy, dz = p.x - c.x, p.y - c.y, p.z - c.z
    return (dx * dx + dy * dy + dz * dz) <= maxDist * maxDist
end

RegisterNetEvent('jw_ainpc:ask', function(npcId, message, clientCtx)
    local src = source
    if type(npcId) ~= 'string' or type(message) ~= 'string' then return end
    local npc = core:getNpc(npcId)
    if not npc then return end
    if not nearNpc(src, npc) then
        log('warn', ('player %s sent a message to %s from too far away; ignored'):format(src, npcId))
        return
    end
    core:ask({
        src = src,
        identifier = bridge.getIdentifier(src),
        npcId = npcId,
        message = message,
        ctx = buildContext(src, clientCtx),
        reply = function(text, meta)
            if text then TriggerClientEvent('jw_ainpc:reply', src, npcId, text) end
            if meta and meta.error then log('debug', 'reply meta error: ' .. tostring(meta.error)) end
        end,
    })
end)

AddEventHandler('playerDropped', function()
    local src = source
    -- RAM copy is dropped (persistent memory, if enabled, stays in the DB).
    local ok, id = pcall(bridge.getIdentifier, src)
    if ok and id then core.memory:forgetPlayer(id) end
end)

-- Hourly usage line in the console (spec: log token usage per day).
CreateThread(function()
    while true do
        Wait(60 * 60 * 1000)
        log('info', core:statsLine())
    end
end)

-- ---------------------------------------------------------------- admin commands
local function reply(src, msg)
    if src == 0 then
        print('[jw_ainpc] ' .. msg)
    else
        TriggerClientEvent('chat:addMessage', src, { args = { 'jw_ainpc', msg } })
    end
end

local function reloadConfig()
    local raw = LoadResourceFile(RES, 'config.lua')
    if not raw then return false, 'config.lua not found' end
    -- Runs in the resource's global env so it replaces the global Config, exactly like at startup.
    local chunk, err = load(raw, '@config.lua', 't')
    if not chunk then return false, err end
    local ok, runErr = pcall(chunk)
    if not ok then return false, runErr end
    return true
end

local commands = {}

function commands.reload(src)
    -- config.lua sets the global Config; re-running it replaces the table in place.
    local ok, err = reloadConfig()
    if not ok then return reply(src, 'reload failed: ' .. tostring(err)) end
    core:applyConfig(Config)
    TriggerClientEvent('jw_ainpc:configReloaded', -1)
    reply(src, ('reloaded: %d NPCs, memory and limits reset'):format(#Config.NPCs))
end

function commands.stats(src)
    reply(src, core:statsLine())
    reply(src, ('framework bridge: %s | provider: %s (%s) | key set: %s | persistence: %s')
        :format(bridge.name, Config.Provider.type, Config.Provider.model, getApiKey() and 'yes' or 'NO',
            persistence and 'on' or 'off'))
end

function commands.test(src, args)
    local npcId = args[2]
    local msg = table.concat(args, ' ', 3)
    if not npcId or msg == '' then return reply(src, 'usage: ainpc test <npcId> <message>') end
    if not core:getNpc(npcId) then return reply(src, 'unknown npc: ' .. npcId) end
    reply(src, ('> [%s] %s'):format(npcId, msg))
    core:ask({
        src = src, identifier = 'console-test', npcId = npcId, message = msg,
        ctx = { playerName = 'Test Player', job = 'unemployed', money = 'modestly off', hour = 21, weather = 'clear' },
        reply = function(text, meta)
            reply(src, ('< [%s] %s'):format(npcId, tostring(text)))
            if meta and meta.actions then
                for _, a in ipairs(meta.actions) do reply(src, ('  action: %s %s'):format(a.name, tostring(a.arg))) end
            end
            if meta and meta.error then reply(src, '  error: ' .. tostring(meta.error)) end
            if meta and meta.blocked then reply(src, '  blocked: ' .. tostring(meta.blocked)) end
        end,
    })
end

function commands.list(src)
    for _, npc in ipairs(Config.NPCs) do reply(src, ('%s - %s'):format(npc.id, npc.name)) end
end

function commands.forget(src, args)
    local id = args[2]
    if not id then return reply(src, 'usage: ainpc forget <identifier>') end
    core.memory:forgetPlayer(id)
    if persistence then persistence.forget(id) end
    reply(src, 'forgot memory for ' .. id)
end

RegisterCommand('ainpc', function(src, args)
    local sub = commands[args[1] or '']
    if not sub then
        return reply(src, 'usage: ainpc <reload|stats|test|list|forget>')
    end
    sub(src, args)
end, true) -- restricted: needs ace permission command.ainpc (console always allowed)

CreateThread(function()
    log('info', ('v%s started | bridge: %s | provider: %s | NPCs: %d | key: %s'):format(
        AINPC.VERSION, bridge.name, Config.Provider.type, #Config.NPCs, getApiKey() and 'set' or 'MISSING'))
    if not getApiKey() and Config.Provider.type ~= 'openai_compat' then
        log('warn', 'No API key. Add to server.cfg:  set ' .. (Config.ApiKeyConvar or 'jw_ainpc_key') .. ' "your-key"')
    end
end)
