# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project scaffolding and documentation
- Product Requirements Document (PRD)
- Implementation Plan (PLAN)
- Competitive analysis of Ecwid SMS marketplace
- Marketplace submission guide
- FastAPI backend with SQLite (WAL mode) and 5 tables
- kwtSMS API client: send, balance, senderid, coverage, validate endpoints
- Ecwid webhook handler with HMAC-SHA256 signature verification
- Ecwid iframe payload decryption (AES-128-CBC)
- SMS processing pipeline: phone normalization, message cleaning, template rendering
- Fernet encryption for credentials at rest
- APScheduler daily sync job for balance, Sender IDs, and coverage
- 6-tab settings UI (General, Gateway, Templates, Integrations, Logs, Help)
- Bilingual support: English and Arabic with RTL layout
- i18n system with en.json and ar.json translation files
- Docker and Docker Compose configuration for production and development
