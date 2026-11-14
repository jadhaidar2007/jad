-- Optional: the resource creates this table itself when Config.Persistence.enabled = true.
CREATE TABLE IF NOT EXISTS `jw_ainpc_memory` (
    `identifier` VARCHAR(64) NOT NULL,
    `npc_id` VARCHAR(64) NOT NULL,
    `history` LONGTEXT NOT NULL,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`identifier`, `npc_id`)
);
