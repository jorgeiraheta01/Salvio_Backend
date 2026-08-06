ALTER TABLE platform_charges
  DROP KEY uq_platform_charges_invoice_number,
  DROP COLUMN invoice_number;
