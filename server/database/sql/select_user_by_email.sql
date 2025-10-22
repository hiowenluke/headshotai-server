SELECT u.id, u.username, u.email, u.coin_balance, u.last_login_at, u.last_login_ip,
       u.created_at, u.updated_at, NULL AS provider, NULL AS provider_sub, NULL AS name, NULL AS picture
FROM public.users u
WHERE u.email=%(email)s
LIMIT 1;
