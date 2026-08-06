-- El texto de diagnostico escrito a mano por el medico (no el resultado de un
-- item del catalogo CIE-10, que si es corto) puede ser un parrafo largo con
-- diagnostico principal/asociados/impresion diagnostica -- VARCHAR(255) lo
-- trunca. Se amplia a TEXT para admitir ambos casos sin limite artificial.
ALTER TABLE record_diagnoses
  MODIFY COLUMN cie10_description TEXT NOT NULL;
