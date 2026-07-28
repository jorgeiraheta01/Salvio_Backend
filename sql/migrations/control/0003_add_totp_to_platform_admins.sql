ALTER TABLE platform_admins
  ADD COLUMN totp_secret_encrypted VARCHAR(255) NULL,
  ADD COLUMN totp_confirmed_at DATETIME NULL;

CREATE TABLE IF NOT EXISTS recovery_codes (
  id BINARY(16) NOT NULL PRIMARY KEY,
  admin_id BINARY(16) NOT NULL,
  code_hash VARCHAR(64) NOT NULL,
  used_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_recovery_admin (admin_id),
  CONSTRAINT fk_recovery_admin FOREIGN KEY (admin_id) REFERENCES platform_admins (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
