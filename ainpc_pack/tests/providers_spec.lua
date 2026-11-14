local H = require('helper')

describe('Providers', function()
    local prompt
    before_each(function()
        H.reset()
        prompt = { system = 'SYS', messages = { { role = 'user', content = 'hi' } } }
    end)

    describe('anthropic', function()
        local P
        before_each(function() P = AINPC.Providers.anthropic end)

        it('builds a Messages API request', function()
            local url, method, body, headers = P.buildRequest({ model = 'm', maxTokens = 50, temperature = 0.5 },
                'KEY', prompt, json)
            assert.equal('https://api.anthropic.com/v1/messages', url)
            assert.equal('POST', method)
            assert.equal('KEY', headers['x-api-key'])
            assert.equal('2023-06-01', headers['anthropic-version'])
            assert.equal('application/json', headers['Content-Type'])
            local b = json.decode(body)
            assert.equal('m', b.model)
            assert.equal(50, b.max_tokens)
            assert.equal('SYS', b.system)
            assert.equal(0.5, b.temperature)
            assert.same(prompt.messages, b.messages)
        end)

        it('parses text and usage', function()
            local status, body = H.anthropicOk('Hello.', 12, 3)
            local ok, text, usage = P.parseResponse(status, body, json)
            assert.is_true(ok)
            assert.equal('Hello.', text)
            assert.same({ input = 12, output = 3 }, usage)
        end)

        it('reports API errors', function()
            local ok, _, _, err = P.parseResponse(401,
                '{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}', json)
            assert.is_false(ok)
            assert.truthy(err:find('invalid x-api-key', 1, true))
        end)

        it('handles empty or garbage bodies', function()
            assert.is_false((P.parseResponse(0, '', json)))
            assert.is_false((P.parseResponse(200, '<html>', json)))
            assert.is_false((P.parseResponse(200, '{"content":[]}', json)))
        end)
    end)

    describe('openai_compat', function()
        local P
        before_each(function() P = AINPC.Providers.openai_compat end)

        it('puts the system prompt first and sets bearer auth', function()
            local url, _, body, headers = P.buildRequest({ url = 'http://x/v1/chat/completions', model = 'llama' },
                'K', prompt, json)
            assert.equal('http://x/v1/chat/completions', url)
            assert.equal('Bearer K', headers.Authorization)
            local b = json.decode(body)
            assert.equal('system', b.messages[1].role)
            assert.equal('SYS', b.messages[1].content)
            assert.equal('hi', b.messages[2].content)
        end)

        it('omits auth for keyless local servers', function()
            local _, _, _, headers = P.buildRequest({}, nil, prompt, json)
            assert.is_nil(headers.Authorization)
        end)

        it('parses a chat completion', function()
            local ok, text, usage = P.parseResponse(200, json.encode({
                choices = { { message = { role = 'assistant', content = 'Yo.' } } },
                usage = { prompt_tokens = 9, completion_tokens = 2 },
            }), json)
            assert.is_true(ok); assert.equal('Yo.', text); assert.same({ input = 9, output = 2 }, usage)
        end)

        it('reports string and object errors', function()
            local ok, _, _, err = P.parseResponse(429, '{"error":{"message":"rate limited"}}', json)
            assert.is_false(ok); assert.truthy(err:find('rate limited', 1, true))
            ok, _, _, err = P.parseResponse(500, '{"error":"boom"}', json)
            assert.is_false(ok); assert.truthy(err:find('boom', 1, true))
        end)
    end)
end)
