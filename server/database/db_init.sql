-- PostgreSQL schema initialization for headshot-ai
-- Run once in development to create required tables & indexes.
-- Safe to re-run (uses IF NOT EXISTS / drops & recreates trigger only).

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

-- Users table
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(50) NOT NULL UNIQUE,
  email VARCHAR(255) NOT NULL UNIQUE,
  coin_balance BIGINT NOT NULL DEFAULT 0,
  last_login_at TIMESTAMPTZ,
  last_login_ip VARCHAR(45),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);

-- Products catalog
CREATE TABLE IF NOT EXISTS products (
  id UUID PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO products (id, slug, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'headshot-ai', 'Headshot AI')
ON CONFLICT (slug) DO UPDATE
SET id = EXCLUDED.id,
    name = EXCLUDED.name;

-- Services catalog (per product)
CREATE TABLE IF NOT EXISTS services (
  id UUID PRIMARY KEY,
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(product_id, code)
);

INSERT INTO services (id, product_id, code, name)
VALUES
  ('00000000-0000-0000-0000-000000020001', '00000000-0000-0000-0000-000000000001', '1P', 'Single Photo'),
  ('00000000-0000-0000-0000-000000020020', '00000000-0000-0000-0000-000000000001', '20P', '20 Photo Pack'),
  ('00000000-0000-0000-0000-000000020040', '00000000-0000-0000-0000-000000000001', '40P', '40 Photo Pack'),
  ('00000000-0000-0000-0000-000000020080', '00000000-0000-0000-0000-000000000001', '80P', '80 Photo Pack'),
  ('00000000-0000-0000-0000-000000020500', '00000000-0000-0000-0000-000000000001', 'DIY', 'DIY Credits'),
  ('00000000-0000-0000-0000-000000029000', '00000000-0000-0000-0000-000000000001', 'TEAM', 'Team Plan')
ON CONFLICT (product_id, code) DO UPDATE
SET id = EXCLUDED.id,
    name = EXCLUDED.name;

-- Updated-at trigger
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at ON users;
CREATE TRIGGER set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION trg_set_updated_at();

-- Coin top-up records
CREATE TABLE IF NOT EXISTS coin_topups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001' REFERENCES products(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  amount_cents BIGINT NOT NULL,
  coins_purchased BIGINT NOT NULL,
  coins_bonus BIGINT NOT NULL DEFAULT 0,
  coins_total BIGINT NOT NULL,
  payment_provider VARCHAR(30),
  payment_tx_id VARCHAR(100),
  status VARCHAR(20) NOT NULL DEFAULT 'succeeded',
  CONSTRAINT chk_topups_nonneg CHECK (
    amount_cents >= 0 AND coins_purchased >= 0 AND coins_bonus >= 0 AND
    coins_total = coins_purchased + coins_bonus
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_coin_topups_provider_tx ON coin_topups(payment_provider, payment_tx_id);
CREATE INDEX IF NOT EXISTS idx_coin_topups_user_time ON coin_topups(user_id, created_at DESC);

-- Coin spending records
CREATE TABLE IF NOT EXISTS coin_spendings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001' REFERENCES products(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  service_id UUID NOT NULL REFERENCES services(id),
  service_quantity INT NOT NULL,
  coin_unit_price BIGINT NOT NULL,
  coins_spent BIGINT NOT NULL,
  CONSTRAINT chk_spend_positive CHECK (
    service_quantity > 0 AND coin_unit_price >= 0 AND coins_spent = service_quantity * coin_unit_price
  )
);
CREATE INDEX IF NOT EXISTS idx_coin_spendings_user_time ON coin_spendings(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coin_spendings_service_id ON coin_spendings(service_id);

-- User identities (OAuth providers linkage)
CREATE TABLE IF NOT EXISTS public.user_identities (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  provider_sub TEXT NOT NULL,
  name TEXT,
  picture TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(provider, provider_sub)
);
CREATE INDEX IF NOT EXISTS idx_user_identities_user ON public.user_identities(user_id);

-- Optional seed (commented):
-- INSERT INTO users (username, email) VALUES ('devuser', 'dev@example.com') ON CONFLICT DO NOTHING;
