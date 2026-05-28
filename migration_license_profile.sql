CREATE TABLE IF NOT EXISTS license_profiles (
    id              SERIAL PRIMARY KEY,
    license_id      INTEGER REFERENCES licenses(id) ON DELETE CASCADE,
    firma_adi       VARCHAR(128),
    yetkili_adi     VARCHAR(128),
    vergi_no        VARCHAR(20),
    vergi_dairesi   VARCHAR(64),
    tc_no           VARCHAR(11),
    telefon         VARCHAR(20),
    email           VARCHAR(120),
    province        VARCHAR(64),
    district        VARCHAR(64),
    neighborhood    VARCHAR(64),
    address         TEXT,
    notlar          TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
