--[[ Headless boot simulation (substitute for a real FXServer boot, which could not be downloaded here).
  1. Runs fxmanifest.lua in a metadata DSL sandbox and records every directive.
  2. Resolves every script/file pattern; fails if a pattern matches nothing or a file is missing.
  3. Loads shared+server scripts in manifest order with stubbed server natives, then runs
     `ainpc stats`, `ainpc list`, `ainpc test ...` (fake or live HTTP), and a simulated net event.
  4. Loads shared+client scripts in a separate VM with stubbed client natives, runs one streaming tick.
  Usage: lua5.4 tools/boot_sim.lua [--live]   (run from ainpc_pack/; --live uses ANTHROPIC_API_KEY, max 3 calls)
]]
local RES_DIR = 'jw_ainpc/'
local LIVE = arg[1] == '--live'
local json = require('dkjson')
local failures = 0
local function fail(msg) failures = failures + 1; print('FAIL ' .. msg) end
local function ok(msg) print('ok   ' .. msg) end

-- ------------------------------------------------------------------ manifest
local meta = {}
local manifestEnv = setmetatable({}, { __index = function(_, key)
    return function(value)
        meta[key] = meta[key] or {}
        if type(value) == 'table' then
            for _, v in ipairs(value) do table.insert(meta[key], v) end
        else
            table.insert(meta[key], value)
        end
        -- support `my_data 'x' { ... }` chaining
        return function() end
    end
end })
local chunk = assert(loadfile(RES_DIR .. 'fxmanifest.lua', 't', manifestEnv))
chunk()
ok('fxmanifest.lua parsed: fx_version=' .. meta.fx_version[1] .. ' game=' .. meta.game[1])
if meta.lua54 and meta.lua54[1] ~= 'yes' then fail('lua54 must be yes for escrow') end

local function ls(dir)
    local p = io.popen('ls -1 "' .. RES_DIR .. dir .. '" 2>/dev/null')
    local out = {}
    for line in p:lines() do out[#out + 1] = line end
    p:close()
    return out
end

local function resolve(pattern)
    if not pattern:find('*', 1, true) then
        local f = io.open(RES_DIR .. pattern)
        if f then f:close(); return { pattern } end
        return {}
    end
    local dir, glob = pattern:match('^(.-)/?([^/]*)$')
    local lpat = '^' .. glob:gsub('%.', '%%.'):gsub('%*', '.*') .. '$'
    local out = {}
    for _, name in ipairs(ls(dir)) do
        if name:match(lpat) then out[#out + 1] = (dir ~= '' and dir .. '/' or '') .. name end
    end
    table.sort(out)
    return out
end

local function expand(key)
    local out = {}
    for _, pat in ipairs(meta[key] or {}) do
        local files = resolve(pat)
        if #files == 0 then fail(key .. ' pattern matches nothing: ' .. pat) end
        for _, f in ipairs(files) do out[#out + 1] = f end
    end
    return out
end

local shared, server, client = expand('shared_scripts'), expand('server_scripts'), expand('client_scripts')
local files = expand('files')
expand('escrow_ignore')
if #resolve(meta.ui_page[1]) == 0 then fail('ui_page missing') end
ok(('manifest resolves: %d shared, %d server, %d client, %d files'):format(#shared, #server, #client, #files))

-- ------------------------------------------------------------------ common stubs
local function vec(x, y, z, w)
    local v = { x = x, y = y, z = z, w = w }
    return setmetatable(v, {
        __sub = function(a, b) return vec(a.x - b.x, a.y - b.y, a.z - b.z) end,
        __len = function(a) return math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z) end,
    })
end

local function makeEnv(side)
    local env = setmetatable({}, { __index = _G })
    env._G = env
    env.json = { encode = function(t) return json.encode(t) end, decode = function(s) return json.decode(s) end }
    env.vector3 = function(x, y, z) return vec(x, y, z) end
    env.vector4 = vec
    env.joaat = function(s) local h = 0; for i = 1, #s do h = (h * 31 + s:byte(i)) % 2 ^ 32 end; return h end
    env.threads, env.events, env.netEvents, env.commands, env.nuiCallbacks = {}, {}, {}, {}, {}
    env.exportsDefined = {}
    env.CreateThread = function(fn) env.threads[#env.threads + 1] = coroutine.create(fn) end
    env.Wait = function(ms) coroutine.yield(ms) end
    env.SetTimeout = function(ms, fn) env.timers = env.timers or {}; env.timers[#env.timers + 1] = { ms = ms, fn = fn } end
    env.GetCurrentResourceName = function() return 'jw_ainpc' end
    env.GetResourceState = function() return 'missing' end
    env.RegisterNetEvent = function(name, fn) env.netEvents[name] = fn; if fn then env.events[name] = fn end end
    env.AddEventHandler = function(name, fn)
        env.events[name] = env.events[name] or {}
        if type(env.events[name]) == 'function' then env.events[name] = { env.events[name] } end
        table.insert(env.events[name], fn)
    end
    env.TriggerEvent = function(name, ...)
        local h = env.events[name]
        if type(h) == 'function' then h(...) elseif type(h) == 'table' then for _, f in ipairs(h) do f(...) end end
    end
    env.RegisterCommand = function(name, fn, restricted) env.commands[name] = { fn = fn, restricted = restricted } end
    env.exports = setmetatable({}, { __call = function(_, name, fn) env.exportsDefined[name] = fn end })
    env.print = function(...)
        local parts = {}
        for i = 1, select('#', ...) do parts[#parts + 1] = tostring(select(i, ...)) end
        local line = (table.concat(parts, ' '):gsub('%^%d', ''))
        if line:find('failed', 1, true) and line:find('reload', 1, true) then fail(line) end
        io.write('     [' .. side .. '] ', line, '\n')
    end
    return env
end

local function loadInto(env, list, label)
    for _, f in ipairs(list) do
        local fn, err = loadfile(RES_DIR .. f, 't', env)
        if not fn then fail(label .. ' syntax ' .. f .. ': ' .. err)
        else
            local good, runErr = pcall(fn)
            if not good then fail(label .. ' load ' .. f .. ': ' .. tostring(runErr)) end
        end
    end
end

local function runThreads(env, steps)
    for _ = 1, steps or 1 do
        for _, co in ipairs(env.threads) do
            if coroutine.status(co) == 'suspended' then
                local good, err = coroutine.resume(co)
                if not good then fail('thread error: ' .. tostring(err)) end
            end
        end
    end
end

-- ------------------------------------------------------------------ server VM
local S = makeEnv('server')
local liveCalls = 0
S.GetConvar = function(name, default)
    if name == 'jw_ainpc_key' then return LIVE and os.getenv('ANTHROPIC_API_KEY') or 'sim-key' end
    return default
end
S.PerformHttpRequest = function(url, cb, method, body, headers)
    assert(method == 'POST', 'POST expected')
    assert(json.decode(body), 'body must be json')
    assert(headers['x-api-key'], 'x-api-key header expected')
    if LIVE then
        liveCalls = liveCalls + 1
        if liveCalls > 3 then return cb(0, '{"error":{"message":"live cap reached"}}') end
        local tmp = os.tmpname()
        local f = io.open(tmp, 'w'); f:write(body); f:close()
        local hdr = {}
        for k, v in pairs(headers) do hdr[#hdr + 1] = ("-H '%s: %s'"):format(k, v) end
        local p = io.popen(("curl -sS -w '\\n%%{http_code}' %s --data-binary @%s '%s'")
            :format(table.concat(hdr, ' '), tmp, url))
        local out = p:read('a'); p:close(); os.remove(tmp)
        local respBody, code = out:match('^(.*)\n(%d+)$')
        return cb(tonumber(code), respBody)
    end
    cb(200, json.encode({
        content = { { type = 'text', text = 'Evening, pal. Quiet night so far. [ACTION:give_hint:heist_1]' } },
        usage = { input_tokens = 420, output_tokens = 18 },
    }))
end
S.GetPlayerName = function() return 'SimPlayer' end
S.GetPlayerIdentifierByType = function() return 'license:sim' end
S.GetPlayerPed = function() return 1 end
S.GetEntityCoords = function() return vec(128.0, -1283.0, 29.27) end
S.TriggerClientEvent = function(name, target, ...)
    S.clientEvents = S.clientEvents or {}
    table.insert(S.clientEvents, { name = name, target = target, args = { ... } })
end
S.LoadResourceFile = function(_, path)
    local f = io.open(RES_DIR .. path); if not f then return nil end
    local s = f:read('a'); f:close(); return s
end

loadInto(S, shared, 'server')
loadInto(S, server, 'server')
runThreads(S, 1)
if failures == 0 then ok('all server scripts loaded with no errors') end

local cmd = S.commands.ainpc
if not cmd then fail('ainpc command not registered') else
    if not cmd.restricted then fail('ainpc command must be restricted') end
    cmd.fn(0, { 'stats' })
    cmd.fn(0, { 'list' })
    cmd.fn(0, { 'test', 'unicorn_bartender', 'Any', 'gossip', 'tonight?' })
    cmd.fn(0, { 'test', 'nope', 'hi' })
    cmd.fn(0, { 'reload' })
    ok('admin commands ran')
end

-- simulated player message over the network
S.source = 7
S.netEvents['jw_ainpc:ask']('unicorn_bartender', 'Hello there', { hour = 22, weather = 'rain' })
local got
for _, e in ipairs(S.clientEvents or {}) do if e.name == 'jw_ainpc:reply' and e.target == 7 then got = e end end
if got then ok('net event jw_ainpc:ask -> jw_ainpc:reply: "' .. got.args[2] .. '"')
else fail('no reply event sent to player') end

-- far-away player must be ignored
S.GetEntityCoords = function() return vec(2000.0, 2000.0, 30.0) end
local before = #(S.clientEvents or {})
S.source = 8
S.netEvents['jw_ainpc:ask']('unicorn_bartender', 'Hello from far away', {})
if #(S.clientEvents or {}) ~= before then fail('far player got a reply') else ok('far-away player ignored') end

-- ------------------------------------------------------------------ client VM
local C = makeEnv('client')
local nop = function() return 0 end
for _, n in ipairs({ 'SetNuiFocus', 'SendNUIMessage', 'TriggerServerEvent', 'SetModelAsNoLongerNeeded',
    'SetEntityAsMissionEntity', 'SetEntityInvincible', 'FreezeEntityPosition', 'SetBlockingOfNonTemporaryEvents',
    'SetPedFleeAttributes', 'SetPedCanRagdoll', 'SetPedDiesWhenInjured', 'TaskStartScenarioInPlace',
    'TaskTurnPedToFaceEntity', 'TaskLookAtEntity', 'ClearPedTasks', 'DeletePed', 'RemoveBlip', 'SetBlipSprite',
    'SetBlipScale', 'SetBlipAsShortRange', 'BeginTextCommandSetBlipName', 'AddTextComponentSubstringPlayerName',
    'EndTextCommandSetBlipName', 'BeginTextCommandDisplayHelp', 'EndTextCommandDisplayHelp', 'RequestModel' }) do
    C[n] = nop
end
local pedsCreated = 0
C.PlayerPedId = function() return 1 end
C.GetEntityCoords = function() return vec(128.0, -1283.0, 29.27) end
C.GetEntityHeading = function() return 0.0 end
C.IsModelInCdimage = function() return true end
C.HasModelLoaded = function() return true end
C.GetGameTimer = function() return 0 end
C.CreatePed = function() pedsCreated = pedsCreated + 1; return 100 + pedsCreated end
C.DoesEntityExist = function() return true end
C.AddBlipForCoord = function() return 1 end
C.IsControlJustReleased = function() return false end
C.IsEntityDead = function() return false end
C.GetClockHours = function() return 22 end
C.GetPrevWeatherTypeHashName = function() return 0 end
C.RegisterNUICallback = function(name, fn) C.nuiCallbacks[name] = fn end

loadInto(C, shared, 'client')
loadInto(C, client, 'client')
runThreads(C, 2)
if pedsCreated > 0 then ok(('client streaming tick spawned %d ped(s) near the player'):format(pedsCreated))
else fail('client spawned no peds near the bartender') end
if C.nuiCallbacks.send and C.nuiCallbacks.close then ok('NUI callbacks registered') else fail('NUI callbacks missing') end
C.AINPC.OpenChat(C.Config.NPCs[1])
C.nuiCallbacks.send({ message = 'hi' }, function() end)
C.nuiCallbacks.close({}, function() end)
ok('client open/send/close cycle ran')

print(failures == 0 and '\nBOOT SIMULATION PASSED' or ('\nBOOT SIMULATION FAILED: ' .. failures))
os.exit(failures == 0 and 0 or 1)
