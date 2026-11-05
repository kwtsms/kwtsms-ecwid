# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Docs and examples use the placeholder 965XXXXXXXX instead of a sample mobile number.

### Docs
- Test mode hint (English and Arabic): test messages are queued but not delivered; their credits are held until you delete them from the Sending Queue (previously described as consuming no credits)

## [1.0.0] - 2026-03-18

### Added
- FastAPI backend with SQLite (WAL mode) and 5 tables (settings, sms_log, templates, sync_data, debug_log)
- kwtSMS API client: send, balance, senderid, coverage, validate endpoints with rate limiting
- Ecwid webhook handler with HMAC-SHA256 signature verification and async processing
- Ecwid iframe payload decryption (AES-128-CBC) for native app authentication
- SMS processing pipeline: phone normalization, message cleaning, template rendering
- Fernet encryption for credentials at rest
- APScheduler daily sync job for balance, Sender IDs, and coverage
- 6-tab settings UI (General, Gateway, Templates, Integrations, Logs, Help)
- Bilingual support: English and Arabic with RTL layout
- i18n system with en.json and ar.json translation files
- Docker multi-stage build, non-root appuser, Docker Compose for production and development
- Auto-seed 6 default SMS templates on first startup
- application.uninstalled webhook handler to clear credentials on app removal
- Generic error responses with full exception detail logged server-side only
