-- Optional cross-session memory via oxmysql. Off by default (Config.Persistence.enabled).
AINPC = AINPC or {}

local Persistence = {}

function Persistence.create(cfg, json, log)
    if GetResourceState('oxmysql') ~= 'started' then
        log('warn', 'Persistence is enabled but oxmysql is not started; memory will reset on restart.')
        return nil
    end
    local tbl = cfg.table or 'jw_ainpc_memory'
    if not tbl:match('^[%w_]+$') then
        log('error', 'Invalid Persistence.table name; persistence disabled.')
        return nil
    end
    local db = exports.oxmysql

    db:query(([[CREATE TABLE IF NOT EXISTS `%s` (
        `identifier` VARCHAR(64) NOT NULL,
        `npc_id` VARCHAR(64) NOT NULL,
        `history` LONGTEXT NOT NULL,
        `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`identifier`, `npc_id`)
    )]]):format(tbl), {})

    return {
        load = function(identifier, npcId, cb)
            db:query(('SELECT history FROM `%s` WHERE identifier = ? AND npc_id = ?'):format(tbl),
                { identifier, npcId }, function(rows)
                    local list = {}
                    if rows and rows[1] and rows[1].history then
                        local ok, decoded = pcall(json.decode, rows[1].history)
                        if ok and type(decoded) == 'table' then list = decoded end
                    end
                    cb(list)
                end)
        end,
        save = function(identifier, npcId, list)
            db:query(('INSERT INTO `%s` (identifier, npc_id, history) VALUES (?, ?, ?) '
                .. 'ON DUPLICATE KEY UPDATE history = VALUES(history)'):format(tbl),
                { identifier, npcId, json.encode(list) })
        end,
        forget = function(identifier)
            db:query(('DELETE FROM `%s` WHERE identifier = ?'):format(tbl), { identifier })
        end,
    }
end

AINPC.Persistence = Persistence
