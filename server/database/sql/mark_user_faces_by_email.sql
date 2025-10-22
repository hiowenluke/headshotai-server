UPDATE public.users
   SET has_uploaded_faces = TRUE
 WHERE email = %(email)s
   AND has_uploaded_faces IS DISTINCT FROM TRUE;
