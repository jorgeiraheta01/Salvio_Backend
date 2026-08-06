-- Nota: revertir a un unico global es solo seguro si nunca coexistieron
-- dos clinicas con el mismo invoice_number (garantizado si esta migracion
-- se aplico poco despues de la 0008, antes de uso real en produccion).
ALTER TABLE platform_charges
  DROP KEY uq_platform_charges_tenant_invoice,
  ADD UNIQUE KEY uq_platform_charges_invoice_number (invoice_number),
  MODIFY COLUMN invoice_number INT NOT NULL AUTO_INCREMENT;
