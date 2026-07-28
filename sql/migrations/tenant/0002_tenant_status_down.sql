ALTER TABLE tenants ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
UPDATE tenants SET is_active = (status = 'active');
ALTER TABLE tenants DROP COLUMN status;
