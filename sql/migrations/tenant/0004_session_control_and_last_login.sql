ALTER TABLE tenants ADD COLUMN sessions_invalidated_at DATETIME NULL;
ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL;
