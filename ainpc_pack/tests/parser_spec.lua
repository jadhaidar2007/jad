local H = require('helper')

describe('Parser', function()
    local opts
    before_each(function()
        H.reset()
        opts = { actionDefs = Config.Actions, allowed = { 'discount', 'give_hint', 'call_cops' }, maxChars = 300 }
    end)

    it('passes plain text through', function()
        local text, actions = AINPC.Parser.parse('Hey pal, what will it be?', opts)
        assert.equal('Hey pal, what will it be?', text)
        assert.same({}, actions)
    end)

    it('extracts a valid numeric action and strips the tag', function()
        local text, actions = AINPC.Parser.parse('Fine, you drive a hard bargain. [ACTION:discount:15]', opts)
        assert.equal('Fine, you drive a hard bargain.', text)
        assert.same({ { name = 'discount', arg = 15 } }, actions)
    end)

    it('clamps numbers into range', function()
        local _, a = AINPC.Parser.parse('ok [ACTION:discount:90]', opts)
        assert.equal(20, a[1].arg)
        _, a = AINPC.Parser.parse('ok [ACTION:discount:1]', opts)
        assert.equal(5, a[1].arg)
    end)

    it('rejects non-numeric numbers and unknown enum values', function()
        local _, a = AINPC.Parser.parse('ok [ACTION:discount:lots]', opts)
        assert.same({}, a)
        _, a = AINPC.Parser.parse('ok [ACTION:give_hint:bank_vault_codes]', opts)
        assert.same({}, a)
    end)

    it('accepts valid enum and no-arg actions', function()
        local _, a = AINPC.Parser.parse('Here. [ACTION:give_hint:heist_1]', opts)
        assert.same({ { name = 'give_hint', arg = 'heist_1' } }, a)
        _, a = AINPC.Parser.parse('Get out! [ACTION:call_cops]', opts)
        assert.same({ { name = 'call_cops' } }, a)
    end)

    it('ignores actions not defined or not allowed for this NPC, but still strips them', function()
        opts.allowed = { 'call_cops' }
        local text, a = AINPC.Parser.parse('Sure [ACTION:discount:10] [ACTION:give_money:99999]', opts)
        assert.equal('Sure', text)
        assert.same({}, a)
    end)

    it('fires at most one action by default', function()
        local _, a = AINPC.Parser.parse('[ACTION:discount:10] x [ACTION:call_cops]', opts)
        assert.equal(1, #a)
    end)

    it('strips a half-written tag at the end (token limit cut-off)', function()
        local text = AINPC.Parser.parse('Okay then. [ACTION:disc', opts)
        assert.equal('Okay then.', text)
    end)

    it('strips the npc name prefix but not other colons', function()
        opts.npcName = 'Vinnie'
        assert.equal('Hey there.', (AINPC.Parser.parse('Vinnie: Hey there.', opts)))
        assert.equal('Hey there.', (AINPC.Parser.parse('**Vinnie**: Hey there.', opts)))
        assert.equal('Listen: the cops are coming.', (AINPC.Parser.parse('Listen: the cops are coming.', opts)))
    end)

    it('handles names with pattern characters', function()
        opts.npcName = 'Dr. (Mad) Max'
        assert.equal('Hi.', (AINPC.Parser.parse('Dr. (Mad) Max: Hi.', opts)))
    end)

    it('enforces max length', function()
        opts.maxChars = 30
        local text = AINPC.Parser.parse(string.rep('word ', 40), opts)
        assert.is_true(#text <= 33)
    end)

    it('survives garbage input', function()
        assert.equal('', (AINPC.Parser.parse(nil, opts)))
        assert.equal('', (AINPC.Parser.parse('[ACTION:]', opts)))
        assert.equal('', (AINPC.Parser.parse('', nil)))
    end)
end)
