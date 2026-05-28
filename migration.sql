-- Çoklu site desteği için migration

-- 1. site_admins ara tablosu oluştur
CREATE TABLE IF NOT EXISTS site_admins (
    site_id INTEGER REFERENCES sites(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (site_id, user_id)
);

-- 2. Mevcut admin_user_id ilişkisini site_admins tablosuna taşı
INSERT INTO site_admins (site_id, user_id)
SELECT id, admin_user_id FROM sites
WHERE admin_user_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- 3. expenses tablosuna block_id ekle
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS block_id INTEGER REFERENCES blocks(id);
