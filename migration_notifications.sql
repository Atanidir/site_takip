CREATE TABLE IF NOT EXISTS notifications (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(128) NOT NULL,
    message     TEXT,
    link        VARCHAR(256),
    is_read     BOOLEAN DEFAULT FALSE,
    notif_type  VARCHAR(30) DEFAULT 'info',
    created_at  TIMESTAMP DEFAULT NOW()
);
