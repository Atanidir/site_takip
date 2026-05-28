CREATE TABLE IF NOT EXISTS system_settings (
    id              SERIAL PRIMARY KEY,
    scope           VARCHAR(20) DEFAULT 'global',
    site_id         INTEGER REFERENCES sites(id) ON DELETE CASCADE,
    smtp_host       VARCHAR(128),
    smtp_port       INTEGER DEFAULT 587,
    smtp_user       VARCHAR(128),
    smtp_pass       VARCHAR(256),
    smtp_from_name  VARCHAR(64),
    smtp_from_email VARCHAR(128),
    smtp_use_tls    BOOLEAN DEFAULT TRUE,
    netgsm_user     VARCHAR(64),
    netgsm_pass     VARCHAR(128),
    netgsm_header   VARCHAR(20),
    mail_active     BOOLEAN DEFAULT FALSE,
    sms_active      BOOLEAN DEFAULT FALSE,
    updated_at      TIMESTAMP DEFAULT NOW()
);
