ALTER TABLE app_user ADD COLUMN install_id TEXT UNIQUE;
ALTER TABLE source ADD COLUMN baselined BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE source ADD COLUMN last_item_count INT NOT NULL DEFAULT 0;
ALTER TABLE vacancy ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE recruitment ADD COLUMN source_notification_id BIGINT REFERENCES notification(id);
ALTER TABLE recruitment ADD COLUMN extraction_confidence TEXT;     -- high | low | manual
ALTER TABLE recruitment ADD COLUMN extraction_flags TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE notification ADD COLUMN dedupe_key TEXT;
ALTER TABLE notification ADD COLUMN duplicate_of BIGINT REFERENCES notification(id);
CREATE INDEX ON notification (dedupe_key);
CREATE INDEX ON notification (recruitment_id);

CREATE TABLE recruitment_draft (
  id BIGSERIAL PRIMARY KEY,
  notification_id BIGINT NOT NULL UNIQUE REFERENCES notification(id),
  pdf_url TEXT,
  status TEXT NOT NULL DEFAULT 'needs_review'
    CHECK (status IN ('auto_published','needs_review','approved','rejected','failed')),
  extracted JSONB NOT NULL DEFAULT '{}',
  flags TEXT[] NOT NULL DEFAULT '{}',
  recruitment_id BIGINT REFERENCES recruitment(id),
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE system_alert (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  kind TEXT NOT NULL, message TEXT NOT NULL,
  acknowledged BOOLEAN NOT NULL DEFAULT false
);
