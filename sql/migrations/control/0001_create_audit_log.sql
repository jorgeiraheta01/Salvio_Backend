CREATE TABLE IF NOT EXISTS audit_log (
  id BINARY(16) NOT NULL PRIMARY KEY,
  admin_id BINARY(16) NULL,
  tenant_id VARCHAR(50) NULL,
  action VARCHAR(50) NOT NULL,
  table_name VARCHAR(100) NOT NULL,
  record_id BINARY(16) NULL,
  old_values JSON NULL,
  new_values JSON NULL,
  ip_address VARCHAR(45) NULL,
  user_agent TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_control_audit_admin (admin_id),
  INDEX idx_control_audit_tenant (tenant_id),
  INDEX idx_control_audit_action (action),
  INDEX idx_control_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
