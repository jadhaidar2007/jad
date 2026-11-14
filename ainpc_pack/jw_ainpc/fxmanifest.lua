fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'jw_ainpc'
author 'JW Scripts'
description 'AI NPCs that hold real conversations with players (Claude / OpenAI-compatible)'
version '1.0.0'

shared_scripts {
    'shared/init.lua',
    'shared/locale.lua',
    'locales/*.lua',
    'config.lua',
}

client_scripts {
    'client/main.lua',
    'client/nui.lua',
}

server_scripts {
    'server/ratelimit.lua',
    'server/memory.lua',
    'server/parser.lua',
    'server/prompt.lua',
    'server/providers/*.lua',
    'server/core.lua',
    'server/persistence.lua',
    'bridge/standalone.lua',
    'bridge/qb.lua',
    'bridge/qbx.lua',
    'bridge/esx.lua',
    'bridge/init.lua',
    'server/main.lua',
    'examples/*.lua',
}

ui_page 'html/index.html'

files {
    'html/index.html',
    'html/style.css',
    'html/app.js',
}

escrow_ignore {
    'config.lua',
    'locales/*.lua',
    'bridge/*.lua',
    'examples/*.lua',
}
