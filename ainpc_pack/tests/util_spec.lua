local H = require('helper')

describe('Util', function()
    before_each(H.reset)

    it('sanitizes control chars, html brackets and whitespace', function()
        assert.equal('hello there bfriend/b', AINPC.Util.sanitize('  hello\n\tthere <b>friend</b>  ', 200))
        assert.equal('a b', AINPC.Util.sanitize('a\0\1b', 200))
        assert.equal('', AINPC.Util.sanitize(nil))
        assert.equal('', AINPC.Util.sanitize({}))
    end)

    it('caps length', function()
        assert.equal(10, #AINPC.Util.sanitize(string.rep('x', 50), 10))
    end)

    it('never splits a UTF-8 character when cutting', function()
        local arabic = 'مرحبا بك' -- 2 bytes per letter
        local cut = AINPC.Util.utf8Cut(arabic, 5)
        assert.is_true(#cut <= 5)
        assert.truthy(utf8.len(cut), 'cut must be valid utf8')
    end)

    it('truncates on word boundaries with ellipsis', function()
        local out = AINPC.Util.truncateWords('the quick brown fox jumps over the lazy dog', 20)
        assert.equal('the quick brown fox...', out)
        assert.equal('short', AINPC.Util.truncateWords('short', 20))
    end)

    it('detects blocked words as whole words only', function()
        local words = { 'badword' }
        assert.is_true(AINPC.Util.containsBlockedWord('you BADWORD!', words))
        assert.is_false(AINPC.Util.containsBlockedWord('notabadwordhere', words))
        assert.is_false(AINPC.Util.containsBlockedWord('anything', {}))
    end)

    it('maps money to brackets', function()
        local b = { { below = 1000, label = 'broke' }, { below = 20000, label = 'modest', final = 'wealthy' } }
        assert.equal('broke', AINPC.Util.moneyBracket(50, b))
        assert.equal('modest', AINPC.Util.moneyBracket(5000, b))
        assert.equal('wealthy', AINPC.Util.moneyBracket(1e6, b))
        assert.equal('unknown', AINPC.Util.moneyBracket(nil, b))
    end)
end)

describe('Locales', function()
    before_each(H.reset)
    it('every locale has every english key', function()
        for lang, t in pairs(AINPC.Locales) do
            for key in pairs(AINPC.Locales.en) do
                assert.is_not_nil(t[key], ('%s missing %s'):format(lang, key))
            end
        end
    end)
    it('falls back to english then to the key', function()
        Config.Locale = 'xx'
        assert.equal('Send', AINPC.Locale('send'))
        assert.equal('nope', AINPC.Locale('nope'))
    end)
end)
