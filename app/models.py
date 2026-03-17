"""Pydantic models for request/response validation."""

from pydantic import BaseModel


# --- Settings ---

class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingResponse(BaseModel):
    key: str
    value: str
    updated_at: str


# --- Gateway ---

class GatewayLoginRequest(BaseModel):
    username: str
    password: str


class GatewayLoginResponse(BaseModel):
    success: bool
    balance: int | None = None
    sender_ids: list[str] = []
    message: str = ""


class TestSMSRequest(BaseModel):
    phone: str
    message: str
    sender_id: str


class BalanceResponse(BaseModel):
    balance: int
    synced_at: str


# --- Templates ---

class TemplateCreate(BaseModel):
    event_type: str
    lang: str = "en"
    body: str


class TemplateUpdate(BaseModel):
    body: str | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    id: int
    event_type: str
    lang: str
    body: str
    is_active: bool
    updated_at: str


# --- SMS Log ---

class SMSLogEntry(BaseModel):
    id: int
    created_at: str
    event_type: str
    recipient: str
    message: str
    template_key: str | None
    status: str
    api_response: str | None
    msg_id: str | None
    points_charged: int
    balance_after: int


class SMSLogQuery(BaseModel):
    status: str | None = None
    event_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int = 50
    offset: int = 0


# --- Ecwid Webhook ---

class EcwidWebhookPayload(BaseModel):
    eventId: str
    eventCreated: int
    storeId: int
    entityId: int
    eventType: str
    data: dict | None = None


# --- Ecwid Decrypted Payload (from iframe) ---

class EcwidAppPayload(BaseModel):
    store_id: int
    access_token: str
    lang: str = "en"
    view: str = "dashboard"


# --- Integration Settings ---

class IntegrationEventConfig(BaseModel):
    event_type: str
    enabled: bool = True
    recipient: str = "customer"
    template_id: int | None = None


# --- General API Response ---

class APIResponse(BaseModel):
    success: bool
    message: str = ""
    data: dict | None = None
