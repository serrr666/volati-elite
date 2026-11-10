# Security

Volati Elite is experimental software. No independent security certification or production-readiness claim is made.

The desktop interface connects to an authenticated local service bound to loopback. Analysis plugins execute under the current Windows user. Only load plugins and kernel data you trust.

Case databases, notes, cached data, exports and extracted files are stored locally without application-level encryption. They may contain sensitive information. Treat them with the same care as the original evidence.

Symbol downloads may contact upstream services when enabled. Use the offline setting when external lookups are inappropriate. The app does not have a memory-image upload workflow.

The portable executable is currently unsigned. Native crashes, rendering issues and performance problems are still being investigated and tested.

For ordinary bugs, open an issue with a minimal, sanitized example. For a potential vulnerability, do not publish credentials, exploit details involving real systems or private evidence in a public issue. Start with a minimal contact request on the project repository or author profile so disclosure can be coordinated.
