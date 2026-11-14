std = 'lua54'
max_line_length = 130
codes = true
exclude_files = { 'tests/**', '.luarocks/**' }

-- The only globals this resource defines.
globals = { 'AINPC', 'Config' }

read_globals = {
    -- FiveM runtime
    'json', 'vector3', 'vector4', 'joaat', 'exports', 'source',
    'CreateThread', 'Wait', 'SetTimeout', 'Citizen',
    'RegisterNetEvent', 'AddEventHandler', 'TriggerEvent', 'TriggerServerEvent', 'TriggerClientEvent',
    'RegisterCommand', 'RegisterNUICallback', 'SendNUIMessage', 'SetNuiFocus',
    'GetCurrentResourceName', 'GetResourceState', 'LoadResourceFile', 'GetConvar',
    'PerformHttpRequest', 'GetPlayerName', 'GetPlayerIdentifierByType', 'GetPlayerPed', 'GetEntityCoords',
    'GetEntityHeading', 'PlayerPedId', 'GetGameTimer', 'IsModelInCdimage', 'RequestModel', 'HasModelLoaded',
    'SetModelAsNoLongerNeeded', 'CreatePed', 'DeletePed', 'DoesEntityExist', 'SetEntityAsMissionEntity',
    'SetEntityInvincible', 'FreezeEntityPosition', 'SetBlockingOfNonTemporaryEvents', 'SetPedFleeAttributes',
    'SetPedCanRagdoll', 'SetPedDiesWhenInjured', 'TaskStartScenarioInPlace', 'TaskTurnPedToFaceEntity',
    'TaskLookAtEntity', 'ClearPedTasks', 'IsEntityDead', 'IsControlJustReleased',
    'BeginTextCommandDisplayHelp', 'AddTextComponentSubstringPlayerName', 'EndTextCommandDisplayHelp',
    'AddBlipForCoord', 'SetBlipSprite', 'SetBlipScale', 'SetBlipAsShortRange', 'BeginTextCommandSetBlipName',
    'EndTextCommandSetBlipName', 'RemoveBlip', 'GetClockHours', 'GetPrevWeatherTypeHashName',
}

-- fxmanifest DSL
files['jw_ainpc/fxmanifest.lua'] = {
    read_globals = { 'fx_version', 'game', 'lua54', 'name', 'author', 'description', 'version',
        'shared_scripts', 'client_scripts', 'server_scripts', 'ui_page', 'files', 'escrow_ignore' },
}
