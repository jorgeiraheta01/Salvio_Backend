DROP TABLE IF EXISTS recovery_codes;

ALTER TABLE platform_admins
  DROP COLUMN totp_secret_encrypted,
  DROP COLUMN totp_confirmed_at;
