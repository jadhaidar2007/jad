local H = require('helper')

describe('RateLimiter', function()
    before_each(H.reset)

    it('enforces per-player cooldown', function()
        local c = H.clock()
        local rl = AINPC.RateLimiter.new({ cooldownSeconds = 4 }, c)
        assert.is_true(rl:check('a'))
        rl:record('a')
        local ok, reason = rl:check('a')
        assert.is_false(ok); assert.equal('cooldown', reason)
        assert.is_true(rl:check('b'), 'other players unaffected')
        c.t = c.t + 4
        assert.is_true(rl:check('a'))
    end)

    it('enforces daily cap and resets next day', function()
        local c = H.clock()
        local rl = AINPC.RateLimiter.new({ dailyPerPlayer = 2 }, c)
        rl:record('a'); rl:record('a')
        local ok, reason = rl:check('a')
        assert.is_false(ok); assert.equal('daily', reason)
        c.d = '2026-11-15'
        assert.is_true(rl:check('a'))
        assert.equal(0, rl:usedToday('a'))
    end)

    it('enforces global per-minute window', function()
        local c = H.clock()
        local rl = AINPC.RateLimiter.new({ globalPerMinute = 3 }, c)
        rl:record('a'); rl:record('b'); rl:record('c')
        local ok, reason = rl:check('d')
        assert.is_false(ok); assert.equal('global', reason)
        c.t = c.t + 61
        assert.is_true(rl:check('d'))
    end)

    it('enforces global per-day ceiling', function()
        local c = H.clock()
        local rl = AINPC.RateLimiter.new({ globalPerDay = 2 }, c)
        rl:record('a'); rl:record('b')
        local ok, reason = rl:check('z')
        assert.is_false(ok); assert.equal('global_daily', reason)
    end)

    it('treats 0 as unlimited', function()
        local rl = AINPC.RateLimiter.new({ cooldownSeconds = 0, dailyPerPlayer = 0, globalPerMinute = 0 }, H.clock())
        for _ = 1, 100 do rl:record('a') end
        assert.is_true(rl:check('a'))
    end)
end)
