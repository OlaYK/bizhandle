# Security Rotation and Cleanup

## 1. Rotate Secrets
- `SECRET_KEY`
- `DATABASE_URL` credentials
- `OPENAI_API_KEY`
- `GOOGLE_CLIENT_ID` / OAuth credentials if exposed

## 2. Ensure `.env` is not tracked
```bash
git rm --cached .env
```

## 3. Purge historical secrets from git history
Use a history rewrite tool on a clean clone, then force push:

```bash
# install git-filter-repo first
git filter-repo --path .env --invert-paths
git push --force --all
git push --force --tags
```

After rewrite, rotate secrets again (old values may still be compromised).
