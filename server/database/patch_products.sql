BEGIN;

-- 新表
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

-- 新增列（如已有列需判断）
ALTER TABLE coin_topups
  ADD COLUMN IF NOT EXISTS product_id UUID;

UPDATE coin_topups
SET product_id = '00000000-0000-0000-0000-000000000001'
WHERE product_id IS NULL;

ALTER TABLE coin_topups
  ALTER COLUMN product_id SET NOT NULL,
  ADD CONSTRAINT fk_coin_topups_product_id FOREIGN KEY (product_id) REFERENCES products(id);

ALTER TABLE coin_spendings
  ADD COLUMN IF NOT EXISTS product_id UUID;

UPDATE coin_spendings
SET product_id = '00000000-0000-0000-0000-000000000001'
WHERE product_id IS NULL;

ALTER TABLE coin_spendings
  ALTER COLUMN product_id SET NOT NULL,
  ADD CONSTRAINT fk_coin_spendings_product_id FOREIGN KEY (product_id) REFERENCES products(id);

ALTER TABLE coin_spendings
  ADD COLUMN IF NOT EXISTS service_id UUID;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'coin_spendings'
      AND column_name = 'service_type'
  ) THEN
    UPDATE coin_spendings cs
    SET service_id = s.id
    FROM services s
    WHERE cs.service_id IS NULL
      AND s.product_id = cs.product_id
      AND s.code = cs.service_type;
  END IF;
END $$;

ALTER TABLE coin_spendings
  ALTER COLUMN service_id SET NOT NULL;

DO $$
BEGIN
  BEGIN
    ALTER TABLE coin_spendings
      ADD CONSTRAINT fk_coin_spendings_service_id FOREIGN KEY (service_id) REFERENCES services(id);
  EXCEPTION WHEN duplicate_object THEN
    NULL;
  END;
END $$;

DROP INDEX IF EXISTS idx_coin_spendings_service_type;
ALTER TABLE coin_spendings DROP CONSTRAINT IF EXISTS chk_service_type;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'coin_spendings'
      AND column_name = 'service_type'
  ) THEN
    ALTER TABLE coin_spendings DROP COLUMN service_type;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_coin_spendings_service_id ON coin_spendings(service_id);

COMMIT;