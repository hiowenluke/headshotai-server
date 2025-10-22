INSERT INTO public.users (username,email,last_login_at,last_login_ip)
VALUES (%(username)s,%(email)s, now(), %(ip)s)
ON CONFLICT (email) DO UPDATE
  SET last_login_at=excluded.last_login_at,
      last_login_ip=excluded.last_login_ip,
      updated_at=now()
RETURNING id;
