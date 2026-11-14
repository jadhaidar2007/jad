local H = require('helper')

describe('Prompt', function()
    local npc
    before_each(function()
        H.reset()
        npc = Config.NPCs[5] -- ammunation clerk, has discount + call_cops
    end)

    it('includes persona, lore, knowledge, guard, language and length', function()
        local s = AINPC.Prompt.buildSystem(npc, {}, Config)
        assert.truthy(s:find('You are Bud', 1, true))
        assert.truthy(s:find(npc.persona, 1, true))
        assert.truthy(s:find(Config.ServerLore[1], 1, true))
        assert.truthy(s:find(npc.knowledge[1], 1, true))
        assert.truthy(s:find('Never say you are an AI', 1, true))
        assert.truthy(s:find('Always reply in English', 1, true))
        assert.truthy(s:find('under 300 characters', 1, true))
    end)

    it('lists only the actions this NPC may use, with usage format', function()
        local s = AINPC.Prompt.buildSystem(npc, {}, Config)
        assert.truthy(s:find('[ACTION:discount:N] where N is a whole number from 5 to 20', 1, true))
        assert.truthy(s:find('[ACTION:call_cops]', 1, true))
        assert.falsy(s:find('give_hint', 1, true))
    end)

    it('omits the action section when the NPC has none', function()
        local s = AINPC.Prompt.buildSystem(Config.NPCs[2], {}, Config)
        assert.falsy(s:find('ACTION', 1, true))
    end)

    it('injects player and world context', function()
        local s = AINPC.Prompt.buildSystem(npc,
            { playerName = 'Tony Russo', job = 'Mechanic', money = 'broke', hour = 3, weather = 'rain' }, Config)
        assert.truthy(s:find('Tony Russo', 1, true))
        assert.truthy(s:find('Mechanic', 1, true))
        assert.truthy(s:find('They look broke', 1, true))
        assert.truthy(s:find('03:00', 1, true))
        assert.truthy(s:find('rain', 1, true))
    end)

    it('uses the NPC language override', function()
        local custom = { name = 'Jamal', role = 'a vendor', language = 'Arabic' }
        assert.truthy(AINPC.Prompt.buildSystem(custom, {}, Config):find('Always reply in Arabic', 1, true))
    end)

    it('appends the user message after history', function()
        local p = AINPC.Prompt.build(npc, {}, {
            { role = 'user', content = 'hi' }, { role = 'assistant', content = 'yo' },
        }, 'price?', Config)
        assert.equal(3, #p.messages)
        assert.same({ role = 'user', content = 'price?' }, p.messages[3])
    end)

    it('merges into a trailing user turn so roles keep alternating', function()
        local p = AINPC.Prompt.build(npc, {}, { { role = 'user', content = 'hi' } }, 'again', Config)
        assert.equal(1, #p.messages)
        assert.equal('hi\nagain', p.messages[1].content)
    end)

    it('does not mutate the passed history', function()
        local hist = { { role = 'user', content = 'hi' } }
        AINPC.Prompt.build(npc, {}, hist, 'again', Config)
        assert.equal('hi', hist[1].content)
    end)
end)
