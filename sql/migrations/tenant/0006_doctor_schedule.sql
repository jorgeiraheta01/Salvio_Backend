CREATE TABLE IF NOT EXISTS doctor_weekly_hours (
  id BINARY(16) NOT NULL DEFAULT (UUID_TO_BIN(UUID())),
  tenant_id VARCHAR(50) NOT NULL,
  doctor_id BINARY(16) NOT NULL,
  day_of_week SMALLINT NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_doctor_weekly_hours_doctor (tenant_id, doctor_id, day_of_week),
  CONSTRAINT fk_doctor_weekly_hours_doctor FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS doctor_absences (
  id BINARY(16) NOT NULL DEFAULT (UUID_TO_BIN(UUID())),
  tenant_id VARCHAR(50) NOT NULL,
  doctor_id BINARY(16) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  reason TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_doctor_absences_doctor (tenant_id, doctor_id, start_date, end_date),
  CONSTRAINT fk_doctor_absences_doctor FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
