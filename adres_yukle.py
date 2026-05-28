import os
import re
import sys

# Veritabanı bağlantısı
DATABASE_URL = 'postgresql://probissi_aidat:V~&d=5+HpW2?!+2@127.0.0.1:5432/probissi_aidat_db'

import psycopg2

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Tabloları oluştur
print("Tablolar oluşturuluyor...")
cur.execute("""
CREATE TABLE IF NOT EXISTS il (
    id SERIAL PRIMARY KEY,
    ilid INTEGER UNIQUE NOT NULL,
    iladi VARCHAR(64) NOT NULL
);
CREATE TABLE IF NOT EXISTS ilce (
    id SERIAL PRIMARY KEY,
    ilceid INTEGER UNIQUE NOT NULL,
    ilceadi VARCHAR(64) NOT NULL,
    ilid INTEGER
);
CREATE TABLE IF NOT EXISTS mahalle (
    id SERIAL PRIMARY KEY,
    mahalleid INTEGER UNIQUE NOT NULL,
    mahalleadi VARCHAR(256) NOT NULL,
    ilceid INTEGER
);
""")
conn.commit()

BASE = os.path.dirname(os.path.abspath(__file__))

def yukle(dosya, tablo, cols, regex):
    path = os.path.join(BASE, dosya)
    if not os.path.exists(path):
        print(f"HATA: {dosya} bulunamadı!")
        return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    matches = re.findall(regex, content)
    print(f"{dosya}: {len(matches)} kayıt bulundu, yükleniyor...")
    cur.execute(f"DELETE FROM {tablo}")
    batch = []
    placeholders = ','.join(['%s'] * len(cols))
    for i, m in enumerate(matches):
        batch.append(tuple(m[j] for j in range(len(cols))))
        if len(batch) >= 1000:
            cur.executemany(f"INSERT INTO {tablo} ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING", batch)
            batch = []
            sys.stdout.write(f"\r  {i+1}/{len(matches)}")
            sys.stdout.flush()
    if batch:
        cur.executemany(f"INSERT INTO {tablo} ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING", batch)
    conn.commit()
    print(f"\n  {tablo} tamamlandı.")

# İller
yukle('il.sql', 'il',
      ['id','ilid','iladi'],
      r'\((\d+),\s*(\d+),\s*[\'\"](.*?)[\'\"]\)')

# İlçeler
yukle('ilce.sql', 'ilce',
      ['id','ilceid','ilceadi','ilid'],
      r'\((\d+),\s*(\d+),\s*[\'\"](.*?)[\'\"],\s*(\d+)\)')

# Mahalleler - virgül içeren adlar için farklı regex
yukle('mahalle.sql', 'mahalle',
      ['id','mahalleid','mahalleadi','ilceid'],
      r'\((\d+),\s*(\d+),\s*\'((?:[^\'\\]|\\\')*)\',\s*(\d+)\)')

cur.close()
conn.close()
print("TAMAMLANDI!")
