CREATE TABLE IF NOT EXISTS encounters (
    id BINARY(16) PRIMARY KEY,
    appointment_id BINARY(16) NULL,
    patient_id BINARY(16) NOT NULL,
    tenant_id VARCHAR(50) NOT NULL,
    doctor_id BINARY(16) NOT NULL,
    status ENUM('active', 'completed', 'closed') NOT NULL DEFAULT 'active',
    chief_complaint TEXT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    closed_at DATETIME NULL,
    created_by BINARY(16) NULL,
    updated_by BINARY(16) NULL,
    version INT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_encounters_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL,
    CONSTRAINT fk_encounters_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    CONSTRAINT fk_encounters_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_encounters_doctor FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_encounter_tenant ON encounters (tenant_id);
CREATE INDEX idx_encounter_patient ON encounters (patient_id);
CREATE INDEX idx_encounter_appointment ON encounters (appointment_id);
CREATE INDEX idx_encounter_doctor_status ON encounters (tenant_id, doctor_id, status);

CREATE TABLE IF NOT EXISTS clinical_orders (
    id BINARY(16) PRIMARY KEY,
    encounter_id BINARY(16) NOT NULL,
    patient_id BINARY(16) NOT NULL,
    tenant_id VARCHAR(50) NOT NULL,
    ordered_by BINARY(16) NOT NULL,
    order_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    status ENUM('active', 'completed', 'cancelled') NOT NULL DEFAULT 'active',
    scheduled_for DATETIME NULL,
    notes TEXT NULL,
    created_by BINARY(16) NULL,
    updated_by BINARY(16) NULL,
    version INT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_encounter FOREIGN KEY (encounter_id) REFERENCES encounters(id) ON DELETE CASCADE,
    CONSTRAINT fk_orders_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    CONSTRAINT fk_orders_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    CONSTRAINT fk_orders_doctor FOREIGN KEY (ordered_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_clinical_orders_tenant ON clinical_orders (tenant_id);
CREATE INDEX idx_clinical_orders_encounter ON clinical_orders (encounter_id);
CREATE INDEX idx_clinical_orders_status ON clinical_orders (tenant_id, status);

ALTER TABLE vital_signs
    ADD COLUMN encounter_id BINARY(16) NULL AFTER tenant_id,
    ADD COLUMN updated_by BINARY(16) NULL AFTER recorded_by,
    ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER updated_by,
    ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

CREATE INDEX idx_vs_encounter ON vital_signs (encounter_id);

ALTER TABLE record_diagnoses
    MODIFY COLUMN clinical_record_id BINARY(16) NULL,
    ADD COLUMN encounter_id BINARY(16) NULL FIRST,
    ADD COLUMN created_by BINARY(16) NULL AFTER notes,
    ADD COLUMN updated_by BINARY(16) NULL AFTER created_by,
    ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER updated_by,
    ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

CREATE INDEX idx_diag_encounter ON record_diagnoses (encounter_id);

ALTER TABLE clinical_notes
    ADD COLUMN encounter_id BINARY(16) NULL AFTER admission_id,
    ADD COLUMN updated_by BINARY(16) NULL AFTER authored_by_name,
    ADD COLUMN is_closed TINYINT(1) NOT NULL DEFAULT 0 AFTER updated_by,
    ADD COLUMN closed_at DATETIME NULL AFTER is_closed,
    ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER closed_at,
    ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

CREATE INDEX idx_notes_encounter ON clinical_notes (encounter_id);

ALTER TABLE prescriptions
    ADD COLUMN encounter_id BINARY(16) NULL AFTER tenant_id,
    ADD COLUMN updated_by BINARY(16) NULL AFTER status,
    ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER updated_by,
    ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at;

CREATE INDEX idx_rx_encounter ON prescriptions (encounter_id);
