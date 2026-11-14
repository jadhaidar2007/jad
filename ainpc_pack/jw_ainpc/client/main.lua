-- Ped streaming (spawn near, despawn far) and interaction (ox_target / qb-target / E prompt).
local peds = {}          -- npcId -> ped handle
local activeNpc = nil    -- npcId currently in conversation
local interaction = nil  -- resolved interaction mode

local function L(key) return AINPC.Locale(key) end

local function resolveInteraction()
    local mode = Config.Interaction or 'auto'
    if mode ~= 'auto' then return mode end
    if GetResourceState('ox_target') == 'started' then return 'ox_target' end
    if GetResourceState('qb-target') == 'started' then return 'qb-target' end
    return 'prompt'
end

local function loadModel(model)
    local hash = type(model) == 'number' and model or joaat(model)
    if not IsModelInCdimage(hash) then
        print(('[jw_ainpc] ^1invalid ped model: %s^7'):format(tostring(model)))
        return nil
    end
    RequestModel(hash)
    local timeout = GetGameTimer() + 5000
    while not HasModelLoaded(hash) do
        if GetGameTimer() > timeout then return nil end
        Wait(10)
    end
    return hash
end

local function addTarget(npc, ped)
    if interaction == 'ox_target' then
        exports.ox_target:addLocalEntity(ped, { {
            name = 'jw_ainpc_' .. npc.id,
            label = L('talk_to'):format(npc.name),
            icon = 'fa-solid fa-comments',
            distance = Config.InteractDistance,
            onSelect = function() AINPC.OpenChat(npc) end,
        } })
    elseif interaction == 'qb-target' then
        exports['qb-target']:AddTargetEntity(ped, {
            options = { {
                label = L('talk_to'):format(npc.name),
                icon = 'fas fa-comments',
                action = function() AINPC.OpenChat(npc) end,
            } },
            distance = Config.InteractDistance,
        })
    end
end

local function removeTarget(ped)
    if interaction == 'ox_target' then
        exports.ox_target:removeLocalEntity(ped)
    elseif interaction == 'qb-target' then
        exports['qb-target']:RemoveTargetEntity(ped)
    end
end

local function spawn(npc)
    local hash = loadModel(npc.model)
    if not hash then return end
    local c = npc.coords
    local ped = CreatePed(4, hash, c.x, c.y, c.z - 1.0, c.w, false, true)
    SetModelAsNoLongerNeeded(hash)
    if not ped or ped == 0 then return end
    SetEntityAsMissionEntity(ped, true, true)
    SetEntityInvincible(ped, true)
    FreezeEntityPosition(ped, true)
    SetBlockingOfNonTemporaryEvents(ped, true)
    SetPedFleeAttributes(ped, 0, false)
    SetPedCanRagdoll(ped, false)
    SetPedDiesWhenInjured(ped, false)
    if npc.scenario then TaskStartScenarioInPlace(ped, npc.scenario, 0, true) end
    peds[npc.id] = ped
    addTarget(npc, ped)
end

local function despawn(npcId)
    local ped = peds[npcId]
    if not ped then return end
    removeTarget(ped)
    if DoesEntityExist(ped) then DeletePed(ped) end
    peds[npcId] = nil
end

local function despawnAll()
    for id in pairs(peds) do despawn(id) end
end

AINPC.GetPed = function(npcId) return peds[npcId] end

-- Blips (optional per NPC)
local blips = {}
local function refreshBlips()
    for _, b in ipairs(blips) do RemoveBlip(b) end
    blips = {}
    for _, npc in ipairs(Config.NPCs) do
        if npc.blip then
            local b = AddBlipForCoord(npc.coords.x, npc.coords.y, npc.coords.z)
            SetBlipSprite(b, type(npc.blip) == 'table' and npc.blip.sprite or 280)
            SetBlipScale(b, 0.7)
            SetBlipAsShortRange(b, true)
            BeginTextCommandSetBlipName('STRING')
            AddTextComponentSubstringPlayerName(npc.name)
            EndTextCommandSetBlipName(b)
            blips[#blips + 1] = b
        end
    end
end

-- Streaming loop
CreateThread(function()
    interaction = resolveInteraction()
    refreshBlips()
    while true do
        local pos = GetEntityCoords(PlayerPedId())
        for _, npc in ipairs(Config.NPCs) do
            local dist = #(pos - vector3(npc.coords.x, npc.coords.y, npc.coords.z))
            local ped = peds[npc.id]
            if dist < Config.SpawnDistance then
                if not ped or not DoesEntityExist(ped) then spawn(npc) end
            elseif ped and activeNpc ~= npc.id then
                despawn(npc.id)
            end
        end
        Wait(1000)
    end
end)

-- Fallback "press E" prompt when no target resource is running.
CreateThread(function()
    while not interaction do Wait(500) end
    if interaction ~= 'prompt' then return end
    while true do
        local sleep = 500
        if not activeNpc then
            local pos = GetEntityCoords(PlayerPedId())
            for _, npc in ipairs(Config.NPCs) do
                if peds[npc.id] then
                    local dist = #(pos - vector3(npc.coords.x, npc.coords.y, npc.coords.z))
                    if dist < Config.InteractDistance then
                        sleep = 0
                        BeginTextCommandDisplayHelp('STRING')
                        AddTextComponentSubstringPlayerName(L('press_to_talk'):format(npc.name))
                        EndTextCommandDisplayHelp(0, false, true, -1)
                        if IsControlJustReleased(0, 38) then AINPC.OpenChat(npc) end
                        break
                    end
                end
            end
        end
        Wait(sleep)
    end
end)

AINPC.SetActive = function(npcId) activeNpc = npcId end

RegisterNetEvent('jw_ainpc:configReloaded', function()
    -- Config is a shared script; the client keeps its startup copy. Restart the resource to
    -- apply NPC position/model changes on clients. Persona/limit changes apply immediately (server-side).
end)

-- Owner helper: prints your current position as a ready-to-paste vector4.
RegisterCommand('ainpc_coords', function()
    local ped = PlayerPedId()
    local c = GetEntityCoords(ped)
    local line = ('vector4(%.2f, %.2f, %.2f, %.1f)'):format(c.x, c.y, c.z, GetEntityHeading(ped))
    print(line)
    TriggerEvent('chat:addMessage', { args = { 'jw_ainpc', line .. ' (also printed in F8)' } })
end, false)

AddEventHandler('onResourceStop', function(res)
    if res ~= GetCurrentResourceName() then return end
    despawnAll()
    for _, b in ipairs(blips) do RemoveBlip(b) end
end)
