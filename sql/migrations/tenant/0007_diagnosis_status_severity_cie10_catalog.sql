ALTER TABLE record_diagnoses ADD COLUMN status ENUM('active','resolved','chronic','recurrent') NOT NULL DEFAULT 'active';
ALTER TABLE record_diagnoses ADD COLUMN severity ENUM('mild','moderate','severe') NULL;

CREATE TABLE IF NOT EXISTS cie10_catalog (
  id BINARY(16) NOT NULL DEFAULT (UUID_TO_BIN(UUID())),
  code VARCHAR(10) NOT NULL,
  description VARCHAR(255) NOT NULL,
  category VARCHAR(100) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_cie10_code (code),
  KEY idx_cie10_description (description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
