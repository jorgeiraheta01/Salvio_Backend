ALTER TABLE tenants ADD COLUMN status ENUM('active','suspended','archived') NOT NULL DEFAULT 'active';
UPDATE tenants SET status = IF(is_active = 1, 'active', 'suspended');
ALTER TABLE tenants DROP COLUMN is_active;
