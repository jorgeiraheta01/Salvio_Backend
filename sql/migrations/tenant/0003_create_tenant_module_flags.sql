CREATE TABLE IF NOT EXISTS tenant_module_flags (
  id BINARY(16) NOT NULL DEFAULT (UUID_TO_BIN(UUID())),
  tenant_id VARCHAR(50) NOT NULL,
  module_key VARCHAR(50) NOT NULL,
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_tenant_module (tenant_id, module_key),
  KEY idx_tenant_module_flags_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
