local H = require('helper')

describe('Bridge detection', function()
    before_each(H.reset)

    local function states(map) return function(res) return map[res] or 'missing' end end

    it('falls back to standalone', function()
        assert.equal('standalone', AINPC.detectBridge('auto', states({})).name)
    end)
    it('detects qb-core', function()
        assert.equal('qb', AINPC.detectBridge('auto', states({ ['qb-core'] = 'started' })).name)
    end)
    it('prefers qbx over its qb-core compatibility layer', function()
        assert.equal('qbx', AINPC.detectBridge('auto', states({ ['qb-core'] = 'started', qbx_core = 'started' })).name)
    end)
    it('detects esx', function()
        assert.equal('esx', AINPC.detectBridge('auto', states({ es_extended = 'started' })).name)
    end)
    it('ignores stopped resources', function()
        assert.equal('standalone', AINPC.detectBridge('auto', states({ es_extended = 'stopped' })).name)
    end)
    it('honours a forced setting and falls back on unknown', function()
        assert.equal('esx', AINPC.detectBridge('esx', states({})).name)
        assert.equal('standalone', AINPC.detectBridge('nonsense', states({})).name)
    end)

    it('qb bridge reads PlayerData', function()
        _G.exports = { ['qb-core'] = { GetCoreObject = function(_)
            return { Functions = { GetPlayer = function()
                return { PlayerData = { citizenid = 'ABC123', charinfo = { firstname = 'Tony', lastname = 'Russo' },
                    job = { label = 'Mechanic' }, money = { cash = 100, bank = 900 } } }
            end } }
        end } }
        local b = AINPC.Bridges.qb
        assert.equal('ABC123', b.getIdentifier(1))
        local ctx = b.getContext(1)
        assert.equal('Tony Russo', ctx.playerName)
        assert.equal('Mechanic', ctx.job)
        assert.equal(1000, ctx.moneyAmount)
    end)

    it('esx bridge reads xPlayer', function()
        _G.exports = { es_extended = { getSharedObject = function(_)
            return { GetPlayerFromId = function()
                return { identifier = 'char1:xyz', job = { label = 'Police' },
                    getName = function() return 'Jane Doe' end,
                    getMoney = function() return 50 end,
                    getAccount = function() return { money = 450 } end }
            end }
        end } }
        local b = AINPC.Bridges.esx
        assert.equal('char1:xyz', b.getIdentifier(1))
        local ctx = b.getContext(1)
        assert.equal('Jane Doe', ctx.playerName); assert.equal('Police', ctx.job); assert.equal(500, ctx.moneyAmount)
    end)

    it('framework bridges fall back to standalone when the player is not loaded', function()
        _G.exports = { qbx_core = { GetPlayer = function() return nil end } }
        local b = AINPC.Bridges.qbx
        assert.equal('license:abc7', b.getIdentifier(7))
        assert.equal('Player7', b.getContext(7).playerName)
    end)
end)
