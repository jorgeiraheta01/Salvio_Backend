-- 0008 dejo invoice_number como AUTO_INCREMENT global a la tabla -- pero
-- debe ser correlativo POR CLINICA (cada tenant con su propia secuencia
-- 1, 2, 3...). Se corrige aqui en vez de reescribir 0008 porque esa
-- migracion ya corrio contra salvio_control.
ALTER TABLE platform_charges
  MODIFY COLUMN invoice_number INT NOT NULL,
  DROP KEY uq_platform_charges_invoice_number,
  ADD UNIQUE KEY uq_platform_charges_tenant_invoice (tenant_id, invoice_number);
