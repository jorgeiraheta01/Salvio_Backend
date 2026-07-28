CREATE TABLE IF NOT EXISTS revoked_tokens (
  id BINARY(16) NOT NULL PRIMARY KEY,
  jti VARCHAR(255) NOT NULL,
  admin_id BINARY(16) NOT NULL,
  expires_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_control_revtok_jti (jti),
  INDEX idx_control_revtok_exp (expires_at),
  CONSTRAINT fk_control_revtok_admin FOREIGN KEY (admin_id) REFERENCES platform_admins (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
