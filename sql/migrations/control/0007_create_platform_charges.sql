CREATE TABLE IF NOT EXISTS platform_charges (
  id BINARY(16) NOT NULL PRIMARY KEY,
  tenant_id VARCHAR(50) NOT NULL,
  period_label VARCHAR(100) NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  currency VARCHAR(3) NOT NULL DEFAULT 'USD',
  status ENUM('pending','paid','void') NOT NULL DEFAULT 'pending',
  due_date DATETIME NULL,
  paid_at DATETIME NULL,
  notes TEXT NULL,
  created_by BINARY(16) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_platform_charges_tenant (tenant_id),
  KEY idx_platform_charges_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
