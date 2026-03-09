# kwtSMS for Ecwid

SMS notification plugin for Ecwid e-commerce stores, powered by [kwtSMS](https://www.kwtsms.com) gateway.

## Features

- **Order Notifications**: Automatic SMS on new orders, payment confirmations, shipping updates
- **Bilingual Templates**: English and Arabic (RTL) message templates with placeholders
- **kwtSMS Integration**: Direct integration with Kuwait's leading SMS gateway
- **Settings Dashboard**: 6-tab settings panel embedded in Ecwid admin
- **Message Logging**: Complete log of all sent messages with API responses
- **Daily Sync**: Automatic balance, SenderID, and coverage synchronization

## Requirements

- Python 3.11+
- Docker (recommended) or any WSGI/ASGI server
- kwtSMS account with API access
- Ecwid store with app installation

## Quick Start

1. Clone the repository:
```bash
git clone <repo-url>
cd kwtsms_ecwid
```

2. Copy environment file and configure:
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. Run with Docker:
```bash
docker compose up -d
```

4. For local development (with ngrok for webhook tunneling):
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## Project Structure

```
kwtsms_ecwid/
├── app/                    # FastAPI application
│   ├── main.py             # App entry point
│   ├── config.py           # Settings and constants
│   ├── database.py         # SQLite setup
│   ├── models.py           # Pydantic schemas
│   ├── routers/            # API route handlers
│   ├── services/           # Business logic
│   ├── utils/              # Helpers (phone, message, logger)
│   └── static/             # Frontend (iframe settings UI)
├── docker/                 # Docker configuration
├── .env.example            # Environment template
├── requirements.txt        # Python dependencies
└── README.md
```

## Configuration

See `.env.example` for all available configuration options.

## Documentation

- [Product Requirements](docs/PRD.md)
- [Implementation Plan](docs/PLAN.md)
- [Competitive Analysis](docs/competitive-analysis.md)
- [Marketplace Submission Guide](docs/marketplace-submission-guide.md)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/ecwid` | POST | Ecwid webhook receiver |
| `/api/settings` | GET/PUT | Plugin settings |
| `/api/templates` | GET/POST/PUT/DELETE | SMS templates |
| `/api/logs` | GET/DELETE | Message logs |
| `/api/balance` | GET | kwtSMS balance check |
| `/api/gateway/login` | POST | Verify kwtSMS credentials |
| `/api/test-sms` | POST | Send test message |
| `/iframe/` | GET | Settings page (Ecwid admin iframe) |

## License

Proprietary. Free to use via the Ecwid App Market.

## Support

- kwtSMS Support: https://www.kwtsms.com/support.html
- Plugin Issues: [GitHub Issues](<repo-url>/issues)
