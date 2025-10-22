SELECT u.id, u.username, u.email, u.coin_balance, u.last_login_at, u.last_login_ip,
       u.created_at, u.updated_at, i.provider, i.provider_sub, i.name, i.picture
FROM public.users u
LEFT JOIN public.user_identities i ON i.user_id = u.id
WHERE i.provider_sub = %(provider_sub)s
LIMIT 1;
