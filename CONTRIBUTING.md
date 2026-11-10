# Contributing

This is an early test version. Focused bug reports and small, reviewable improvements are welcome.

For a bug report, include the app version, Windows version, plugin ID, relevant settings, expected behavior and steps to reproduce. Share sanitized logs or a public test image only when needed. Never include private memory captures, credentials or your complete profile folder.

For code changes, explain the problem and resulting behavior. Preserve original evidence values, compatibility with saved cases and all six translations. Add regression coverage for data-loss, filtering, queue or security changes.

Run the relevant checks after building the frontend:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm test
npm run build
```

The project currently uses the Volatility Software License 1.0. Keep license and third-party notices intact.
