# kwtSMS for Ecwid

SMS notification plugin for Ecwid e-commerce stores. Sends automated SMS to customers and admins on order events via the [kwtSMS](https://www.kwtsms.com) gateway. Supports English and Arabic (RTL) templates. Free to use: store owners pay only for kwtSMS credits.

## Features

- Order notifications: new orders, payment status changes, fulfillment updates
- Bilingual templates: English and Arabic with RTL layout
- 6-tab admin UI embedded directly in Ecwid
- Fernet-encrypted credential storage
- Message log with full API response history
- Daily sync of balance, Sender IDs, and coverage data
- Phone normalization: handles Arabic digits, +/00 prefixes, local format

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- kwtSMS account with API credentials and a registered Sender ID
- Ecwid store registered as a native app

## Quick Start (Docker)

```bash
cp .env.example .env
# Edit .env: set APP_SECRET_KEY, ENCRYPTION_KEY, ECWID_APP_ID, ECWID_CLIENT_SECRET
docker compose -f docker/docker-compose.yml up -d
```

The plugin is available at `http://localhost:8000`. Check `GET /health` to confirm it is running.

## Development Setup (with ngrok)

```bash
cp .env.example .env
# Edit .env: add NGROK_AUTHTOKEN for webhook tunneling
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up
```

Ngrok dashboard: `http://localhost:4040`. Copy the tunnel URL and set it as `APP_BASE_URL` and your Ecwid webhook URL.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_SECRET_KEY` | Yes | Random 64-character secret for the application |
| `APP_ENV` | No | `development` or `production` (default: `development`) |
| `APP_DEBUG` | No | Enable verbose logging (default: `true`) |
| `APP_PORT` | No | Port to listen on (default: `8000`) |
| `APP_BASE_URL` | Yes | Public HTTPS URL (e.g., ngrok URL for local dev) |
| `ECWID_APP_ID` | Yes | Client ID from Ecwid developer dashboard |
| `ECWID_CLIENT_SECRET` | Yes | Client secret from Ecwid developer dashboard |
| `ENCRYPTION_KEY` | Yes | Fernet key for credential encryption. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_PATH` | No | SQLite database path (default: `./data/kwtsms_ecwid.db`) |
| `KWTSMS_API_BASE_URL` | No | kwtSMS API base URL (default: `https://www.kwtsms.com/API`) |
| `SYNC_HOUR` | No | Hour for daily sync job, 0-23 UTC (default: `3`) |
| `SYNC_MINUTE` | No | Minute for daily sync job (default: `0`) |

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/iframe` | GET | Settings page for Ecwid admin iframe |
| `/webhook/ecwid` | POST | Ecwid webhook receiver |
| `/api/settings` | GET, PUT | Plugin settings CRUD |
| `/api/settings/init` | POST | Initialize from Ecwid iframe payload |
| `/api/templates` | GET, POST | List and create SMS templates |
| `/api/templates/{id}` | GET, PUT, DELETE | Single template operations |
| `/api/templates/preview` | POST | Render template with sample data |
| `/api/templates/seed` | POST | Seed default templates for all event types |
| `/api/gateway/login` | POST | Verify kwtSMS credentials, fetch Sender IDs |
| `/api/gateway/balance` | GET | Current SMS credit balance |
| `/api/gateway/senderids` | GET | Available Sender IDs |
| `/api/gateway/coverage` | GET | Coverage data by country |
| `/api/gateway/test-sms` | POST | Send test SMS (always test=1) |
| `/api/logs` | GET, DELETE | SMS message log |
| `/api/logs/stats` | GET | Aggregate log statistics |
| `/api/logs/debug` | GET, DELETE | Debug log entries |

## Ecwid App Registration

1. Go to `https://my.ecwid.com/#develop-apps` and create a custom app.
2. Set `iframeUrl` to `{APP_BASE_URL}/iframe`.
3. Set `webhookUrl` to `{APP_BASE_URL}/webhook/ecwid`.
4. Request scopes: `read_store_profile`, `read_orders`, `read_customers`, `add_to_cp`.
5. Copy `client_id` and `client_secret` to your `.env`.

## SMS Template Placeholders

| Placeholder | Description |
|---|---|
| `{order_id}` | Order number |
| `{customer_name}` | Customer full name |
| `{total}` | Order total amount |
| `{currency}` | Currency code (e.g., KWD) |
| `{status}` | Payment or fulfillment status |
| `{tracking}` | Shipment tracking number |
| `{store_name}` | Store name |
| `{date}` | Order date |

Character limits: 160 per page (English/GSM-7), 70 per page (Arabic/Unicode).

## Supported Ecwid Events

| Event | Trigger | Default Recipients |
|---|---|---|
| `order.created` | New order placed | Customer and Admin |
| `order.updated` (payment) | Payment status changed | Customer |
| `order.updated` (fulfillment) | Fulfillment status changed | Customer |

## Project Structure

```
kwtsms_ecwid/
├── app/
│   ├── main.py             - FastAPI entry point, startup/shutdown
│   ├── config.py           - Settings and constants
│   ├── database.py         - SQLite WAL setup, async queries
│   ├── models.py           - Pydantic v2 request/response models
│   ├── routers/            - API route handlers
│   │   ├── webhook.py      - Ecwid webhook receiver
│   │   ├── settings.py     - Settings CRUD
│   │   ├── gateway.py      - kwtSMS gateway operations
│   │   ├── templates.py    - SMS template management
│   │   └── logs.py         - Message log viewer
│   ├── services/
│   │   ├── kwtsms.py       - kwtSMS API client (5 endpoints)
│   │   ├── ecwid.py        - Ecwid payload decryption, webhook verification
│   │   ├── sms.py          - SMS orchestration and template rendering
│   │   ├── encryption.py   - Fernet credential encryption
│   │   └── scheduler.py    - Daily sync job (APScheduler)
│   ├── utils/
│   │   ├── phone.py        - Phone normalization and validation
│   │   ├── message.py      - Message cleaning and page counting
│   │   └── logger.py       - Structured logging to console and database
│   └── static/
│       ├── iframe/         - Settings page HTML, CSS, JS
│       └── i18n/           - English and Arabic translation files
├── docker/                 - Dockerfile and Docker Compose files
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## License

Proprietary. Free to use via the Ecwid App Market.

## Support

- kwtSMS Support: https://www.kwtsms.com/support.html
- kwtSMS API Documentation: https://www.kwtsms.com/doc/KwtSMS.com_API_Documentation_v41.pdf
