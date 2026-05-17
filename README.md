# Dental Clinic Inbound Voice Agent (VAPI Edition)

AI-powered phone receptionist for a Virginia dental clinic. Answers calls, handles Q&A, books appointments on Google Calendar, and emails the clinic owner after every booking.

**How it works:**
1. Patient calls the VAPI phone number
2. VAPI handles the entire voice pipeline (STT → Claude AI → TTS)
3. When Claude needs to book or check the calendar, VAPI calls our webhook
4. Our FastAPI server executes the tool and returns the result
5. VAPI speaks the result back to the patient

## Stack

| Layer | Service |
|-------|---------|
| Voice call + AI | VAPI (free phone number included) |
| AI model | Claude `claude-sonnet-4-6` via VAPI |
| Transcription | Deepgram nova-2 (via VAPI) |
| Voice | Deepgram Aura `aura-asteria-en` (via VAPI) |
| Calendar | Google Calendar API |
| Email notifications | Gmail SMTP |
| Webhook server | FastAPI |

## Setup

### 1. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Fill in .env

Open `.env` and set:

| Variable | Where to get |
|----------|-------------|
| `VAPI_API_KEY` | [dashboard.vapi.ai](https://dashboard.vapi.ai) → Account → API Keys → Private key |
| `SERVER_BASE_URL` | Your ngrok URL (step 4) |
| `SMTP_PASSWORD` | Gmail App Password for naseebullah700000@gmail.com → [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) |
| `GOOGLE_CALENDAR_ID` | Google Calendar → Settings → Integrate calendar → Calendar ID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to service account JSON (step 3) |

Gmail addresses are already configured:
- **Sender:** naseebullah700000@gmail.com
- **Recipient (clinic):** khannn762@gmail.com

### 3. Google Calendar setup (one-time)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **Google Calendar API**
3. Create a **Service Account** → download JSON credentials
4. Save JSON to `credentials/google-service-account.json`
5. In Google Calendar → your clinic calendar → Settings → **Share with specific people**
   → add the service account email → give **"Make changes to events"** permission
6. Copy the **Calendar ID** into `.env`

### 4. Start ngrok

```bash
ngrok http 8000
# Copy the https URL → set as SERVER_BASE_URL in .env
```

### 5. Start the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Verify it's running: open `http://localhost:8000/health` → should return `{"status":"ok"}`

### 6. Create the VAPI assistant (one-time)

```bash
python scripts/setup_vapi.py
```

This will:
- Create the "Nova" assistant in your VAPI account with Claude + your system prompt + 3 tools
- Assign your VAPI free phone number to the assistant
- Print the phone number to call for testing

> If you don't have a phone number yet: go to [dashboard.vapi.ai](https://dashboard.vapi.ai) → Phone Numbers → Buy/import one. Then run the script again.

### 7. Test without calling

```bash
python -m tests.test_vapi_webhook       # simulate VAPI tool calls locally
python -m tests.test_google_calendar    # test calendar booking
python -m tests.test_email_service      # test email to khannn762@gmail.com
```

### 8. Make a test call

Call the phone number printed by `setup_vapi.py`. Nova will answer:
> "Thank you for calling Bright Smiles Dental, this is Nova! How can I help you today?"

Try asking:
- "What are your hours?"
- "Do you accept Delta Dental insurance?"
- "I'd like to book a cleaning for tomorrow morning"

After booking: check Google Calendar + khannn762@gmail.com inbox for the notification email.

## Project Structure

```
dental-voice-agent/
├── main.py                      # FastAPI app
├── config.py                    # Settings from .env
├── routers/
│   └── vapi_webhook.py          # POST /vapi/webhook — handles VAPI tool calls
├── services/
│   ├── google_calendar.py       # Slot check + event creation
│   └── email_service.py         # Gmail SMTP → khannn762@gmail.com
├── tools/                       # Claude tool executors
│   ├── definitions.py           # VAPI/OpenAI tool schemas
│   ├── book_appointment.py
│   ├── check_available_slots.py
│   └── send_email_notification.py
├── prompts/
│   └── system_prompt.py         # Nova persona (also embedded in setup_vapi.py)
├── scripts/
│   └── setup_vapi.py            # One-time VAPI assistant setup
├── utils/
│   └── logging.py
└── tests/
    ├── test_vapi_webhook.py     # Simulate VAPI tool calls
    ├── test_google_calendar.py
    └── test_email_service.py
```

## Customization

All clinic details (name, address, hours, services) are in `.env` — no code changes needed.

To update the assistant after changing the system prompt or tools, re-run:
```bash
python scripts/setup_vapi.py
```
The script detects the existing assistant and updates it in place.
