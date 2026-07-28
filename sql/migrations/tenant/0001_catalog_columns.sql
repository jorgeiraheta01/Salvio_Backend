ALTER TABLE clinical_systems_catalog
  ADD COLUMN description TEXT NULL,
  ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE lab_tests_catalog
  ADD COLUMN sample_type VARCHAR(100) NULL,
  ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;
