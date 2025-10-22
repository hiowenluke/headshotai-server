UPDATE public.users
   SET has_uploaded_faces = TRUE
 WHERE id IN (
         SELECT user_id
           FROM public.user_identities
          WHERE provider_sub = %(provider_sub)s
          LIMIT 1
       )
   AND has_uploaded_faces IS DISTINCT FROM TRUE;
