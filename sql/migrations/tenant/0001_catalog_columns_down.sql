ALTER TABLE lab_tests_catalog
  DROP COLUMN sample_type,
  DROP COLUMN is_active;

ALTER TABLE clinical_systems_catalog
  DROP COLUMN description,
  DROP COLUMN is_active;
