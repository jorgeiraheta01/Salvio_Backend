ALTER TABLE platform_charges
  ADD COLUMN invoice_number INT NOT NULL AUTO_INCREMENT,
  ADD UNIQUE KEY uq_platform_charges_invoice_number (invoice_number);
