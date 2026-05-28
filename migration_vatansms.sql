ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS sms_provider VARCHAR(20) DEFAULT 'vatansms';
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS vatansms_api_id VARCHAR(20);
ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS vatansms_api_key VARCHAR(64);
