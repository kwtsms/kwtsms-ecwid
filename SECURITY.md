# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email: mo@boxlink.net
3. Include a detailed description of the vulnerability
4. Allow 48 hours for an initial response

## Security Measures

### Credential Protection
- API credentials are encrypted at rest using Fernet symmetric encryption
- Credentials are never logged, even in debug mode
- Credentials are never exposed to the frontend or included in API responses
- Environment variables are used for all sensitive configuration

### Webhook Security
- All Ecwid webhooks are verified using HMAC-SHA256 signature validation
- Invalid signatures are rejected with a generic error message
- Webhook payloads are validated against expected schema

### Input Validation
- All user inputs are sanitized to prevent XSS attacks
- Database queries use parameterized statements to prevent SQL injection
- Phone numbers are strictly validated (digits only, length checks)
- Message content is cleaned before processing

### Communication Security
- All external API calls use HTTPS exclusively
- kwtSMS API calls use POST method only (credentials never in URLs)
- Ecwid API calls use Bearer token authentication

### Error Handling
- Generic error messages are returned to prevent information disclosure
- Detailed errors are logged server-side only
- No stack traces or internal details are exposed to users

### Rate Limiting
- API endpoints are rate-limited to prevent abuse
- kwtSMS API calls are limited to 2 requests per second
- Per-phone cooldown of 15 seconds between sends

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | Yes       |

## Dependencies

Dependencies are regularly reviewed for known vulnerabilities. Report any concerns about third-party dependencies to the email above.
