# Security

## Authentication and sessions

- Django session authentication. The session cookie is `HttpOnly`; in production it is
  also `Secure`, as is the CSRF cookie.
- Every write needs the CSRF token in the `X-CSRFToken` header. The web app reads it from
  the `csrftoken` cookie set by `GET /api/auth/me/` or `GET /api/auth/csrf/`.
- New accounts verify their email with a one-time code before they can sign in.
- Passwords are checked by Django's validators and stored with Django's default hasher.

## Authorisation

- Project visibility follows its status (draft, under review, published) and the user's
  role; see [Users and roles](../introduction/roles.md). The same rules guard every
  project endpoint, including run files and data-catalog downloads.
- The Analytics workspace can be limited to analysts by giving its section roles in
  `backend/apps/core/modules.py`;
  it is open to everyone today.

## Secrets

| Secret | Where it lives | Never |
|---|---|---|
| Django secret key, database password, SMTP password | `backend/.env` on each server | committed to git, printed in logs |
| Service credentials, certificates | `cred/` (git-ignored) or the server's own store | committed to git |

`backend/.env.example` is the template and contains no real values. Production refuses
to start with the development secret key.

## Transport and headers

Apache terminates HTTPS (Let's Encrypt), redirects HTTP to HTTPS and sets
`Strict-Transport-Security` and `X-Content-Type-Options: nosniff`. Gunicorn listens on
`127.0.0.1:8012` only.

## Uploaded files

Uploaded areas are opened with GDAL in a temporary folder, validated and converted to a
geometry; the file itself is not kept. Run outputs are served only through the API, after
the project permission check.

## Checks before a release

```bash
cd backend
python manage.py check --deploy --fail-level ERROR
```

The release script runs this check and stops if it fails.
