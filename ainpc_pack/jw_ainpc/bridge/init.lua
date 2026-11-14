-- Picks the framework bridge. 'auto' checks running resources; Qbox before QBCore because Qbox
-- also provides a qb-core compatibility layer.
AINPC = AINPC or {}

local ORDER = { 'qbx', 'qb', 'esx' }

function AINPC.detectBridge(setting, getState)
    getState = getState or GetResourceState
    if setting and setting ~= 'auto' then
        return AINPC.Bridges[setting] or AINPC.Bridges.standalone
    end
    for _, name in ipairs(ORDER) do
        local b = AINPC.Bridges[name]
        if b and b.resource and getState(b.resource) == 'started' then return b end
    end
    return AINPC.Bridges.standalone
end
