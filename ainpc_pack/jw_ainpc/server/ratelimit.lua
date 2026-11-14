-- Rate limiting and cost caps. Pure Lua: time and day are injected so it is unit-testable.
AINPC = AINPC or {}

local RateLimiter = {}
RateLimiter.__index = RateLimiter

-- opts: cooldownSeconds, dailyPerPlayer, globalPerMinute, globalPerDay (0/nil = unlimited)
-- clock: { now = function() -> seconds, day = function() -> 'YYYY-MM-DD' }
function RateLimiter.new(opts, clock)
    local self = setmetatable({}, RateLimiter)
    self.opts = opts or {}
    self.clock = clock or {
        now = os.time,
        day = function() return os.date('%Y-%m-%d') end,
    }
    self:reset()
    return self
end

function RateLimiter:reset()
    self.lastAt = {}
    self.daily = {}
    self.dayKey = nil
    self.globalWindow = {}
    self.globalToday = 0
end

function RateLimiter:_rollDay()
    local today = self.clock.day()
    if today ~= self.dayKey then
        self.dayKey = today
        self.daily = {}
        self.globalToday = 0
    end
end

function RateLimiter:_pruneWindow(now)
    local kept = {}
    for _, t in ipairs(self.globalWindow) do
        if now - t < 60 then kept[#kept + 1] = t end
    end
    self.globalWindow = kept
end

-- Returns true, or false + reason ('cooldown' | 'daily' | 'global' | 'global_daily') + seconds to wait.
function RateLimiter:check(playerKey)
    self:_rollDay()
    local now = self.clock.now()
    local o = self.opts

    local last = self.lastAt[playerKey]
    if last and o.cooldownSeconds and o.cooldownSeconds > 0 and now - last < o.cooldownSeconds then
        return false, 'cooldown', o.cooldownSeconds - (now - last)
    end
    if o.dailyPerPlayer and o.dailyPerPlayer > 0 and (self.daily[playerKey] or 0) >= o.dailyPerPlayer then
        return false, 'daily'
    end
    if o.globalPerDay and o.globalPerDay > 0 and self.globalToday >= o.globalPerDay then
        return false, 'global_daily'
    end
    self:_pruneWindow(now)
    if o.globalPerMinute and o.globalPerMinute > 0 and #self.globalWindow >= o.globalPerMinute then
        return false, 'global', 60 - (now - self.globalWindow[1])
    end
    return true
end

function RateLimiter:record(playerKey)
    self:_rollDay()
    local now = self.clock.now()
    self.lastAt[playerKey] = now
    self.daily[playerKey] = (self.daily[playerKey] or 0) + 1
    self.globalToday = self.globalToday + 1
    self.globalWindow[#self.globalWindow + 1] = now
end

function RateLimiter:usedToday(playerKey)
    self:_rollDay()
    return self.daily[playerKey] or 0
end

AINPC.RateLimiter = RateLimiter
