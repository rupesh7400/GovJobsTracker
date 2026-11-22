-- PostgreSQL schema: All India Govt Jobs Tracker
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE org_category (
  id SERIAL PRIMARY KEY,
  parent_id INT REFERENCES org_category(id),
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE organization (
  id SERIAL PRIMARY KEY,
  category_id INT REFERENCES org_category(id),
  name TEXT NOT NULL UNIQUE,
  short_name TEXT,
  state TEXT,                          -- NULL = central / all-India
  official_domain TEXT NOT NULL
);

-- Source registry: every monitored official page
CREATE TABLE source (
  id SERIAL PRIMARY KEY,
  organization_id INT NOT NULL REFERENCES organization(id),
  url TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK (kind IN ('html_list','rss','sitemap','api','manual_only')),
  css_selector TEXT,
  interval_minutes INT NOT NULL DEFAULT 60,
  status TEXT NOT NULL DEFAULT 'pending_integration'
    CHECK (status IN ('monitored','pending_integration','manual_verification','unavailable','disabled')),
  last_checked_at TIMESTAMPTZ,
  last_success_at TIMESTAMPTZ,
  last_error TEXT,
  consecutive_failures INT NOT NULL DEFAULT 0,
  content_hash TEXT
);

CREATE TABLE recruitment (
  id BIGSERIAL PRIMARY KEY,
  organization_id INT NOT NULL REFERENCES organization(id),
  advertisement_no TEXT,
  title TEXT NOT NULL,
  department TEXT,
  state TEXT, district TEXT, location TEXT,
  total_vacancies INT,                 -- NULL = "Not specified in official notification"
  qualification_levels TEXT[],
  min_age INT, max_age INT, age_relaxation_text TEXT,
  nationality_text TEXT,
  apply_start DATE, apply_end DATE,
  fee_text TEXT, selection_process TEXT, exam_pattern TEXT, pay_text TEXT,
  notification_pdf_url TEXT, apply_url TEXT, official_site_url TEXT,
  pwbd_eligible BOOLEAN,
  extracted_by TEXT NOT NULL DEFAULT 'manual',
  admin_verified BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON recruitment (apply_end);
CREATE INDEX ON recruitment (state);
CREATE INDEX ON recruitment USING gin (qualification_levels);

CREATE TABLE notification (
  id BIGSERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES source(id),
  recruitment_id BIGINT REFERENCES recruitment(id),   -- links results/admit cards to original ad
  type TEXT NOT NULL CHECK (type IN (
    'recruitment','corrigendum','extension','exam_date','admit_card','answer_key','result',
    'merit_list','cutoff','document_verification','interview','final_selection','waiting_list',
    'cancellation','postponement','vacancy_revision','other')),
  title TEXT NOT NULL,
  official_url TEXT NOT NULL,
  pdf_url TEXT,
  published_on DATE,
  fingerprint TEXT NOT NULL UNIQUE,
  verification TEXT NOT NULL DEFAULT 'unverified'
    CHECK (verification IN ('unverified','auto_verified','admin_verified','rejected')),
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_verified_at TIMESTAMPTZ,
  push_sent_at TIMESTAMPTZ
);
CREATE INDEX ON notification (type, first_seen_at DESC);
CREATE INDEX ON notification USING gin (title gin_trgm_ops);

-- Vacancies exactly as printed in the official notification. Never computed.
CREATE TABLE vacancy (
  id BIGSERIAL PRIMARY KEY,
  recruitment_id BIGINT NOT NULL REFERENCES recruitment(id) ON DELETE CASCADE,
  post_name TEXT, department TEXT, state TEXT,
  gender TEXT,
  category TEXT NOT NULL,              -- UR, SC, ST, OBC, EWS, PwBD, ESM or whatever the ad says
  pwbd_subcategory TEXT,
  count INT NOT NULL
);
CREATE INDEX ON vacancy (recruitment_id);

CREATE TABLE app_user (
  id UUID PRIMARY KEY,
  fcm_token TEXT UNIQUE,
  all_alerts BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE subscription (
  user_id UUID REFERENCES app_user(id) ON DELETE CASCADE,
  dimension TEXT NOT NULL CHECK (dimension IN ('organization','state','qualification','category','type')),
  value TEXT NOT NULL,
  PRIMARY KEY (user_id, dimension, value)
);
CREATE TABLE saved_job (
  user_id UUID REFERENCES app_user(id) ON DELETE CASCADE,
  recruitment_id BIGINT REFERENCES recruitment(id),
  PRIMARY KEY (user_id, recruitment_id)
);
CREATE TABLE push_log (
  user_id UUID REFERENCES app_user(id) ON DELETE CASCADE,
  notification_id BIGINT REFERENCES notification(id),
  sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, notification_id)
);
CREATE TABLE source_check_log (
  id BIGSERIAL PRIMARY KEY,
  source_id INT REFERENCES source(id),
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  ok BOOLEAN NOT NULL, http_status INT, new_items INT DEFAULT 0, error TEXT
);
