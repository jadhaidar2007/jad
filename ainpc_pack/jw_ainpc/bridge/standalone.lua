-- Standalone bridge: no framework. Uses the FiveM player name and license identifier.
AINPC = AINPC or {}
AINPC.Bridges = AINPC.Bridges or {}

AINPC.Bridges.standalone = {
    name = 'standalone',
    resource = nil,
    getIdentifier = function(src)
        return GetPlayerIdentifierByType(src, 'license') or ('src:' .. tostring(src))
    end,
    getContext = function(src)
        return { playerName = GetPlayerName(src) }
    end,
}
