CREATE TABLE IF NOT EXISTS platform_announcements (
  id BINARY(16) NOT NULL PRIMARY KEY,
  message TEXT NOT NULL,
  severity ENUM('info','warning','critical') NOT NULL DEFAULT 'info',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_by BINARY(16) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_announcements_active (active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
