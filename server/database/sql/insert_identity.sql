INSERT INTO public.user_identities(user_id,provider,provider_sub,name,picture)
VALUES (%(user_id)s,%(provider)s,%(provider_sub)s,%(name)s,%(picture)s)
ON CONFLICT (provider, provider_sub) DO UPDATE
  SET user_id=EXCLUDED.user_id,
      name=EXCLUDED.name,
      picture=EXCLUDED.picture,
      updated_at=now();
