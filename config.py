from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # VAPI
    vapi_api_key: str
    vapi_phone_number_id: str = ""
    server_base_url: str = "https://placeholder.ngrok.io"

    # Google Calendar (optional — set to 'skip' to use local mock)
    google_calendar_id: str = "skip"
    google_service_account_json: str = "./credentials/google-service-account.json"

    # Email (Resend HTTP API)
    resend_api_key: str = "re_KFm69fGM_JynaMvZpnrqRxq44ods1z3sa"
    clinic_owner_email: str = "naseebullah700000@gmail.com"  # Resend free tier: must be account email until domain verified
    from_email: str = "onboarding@resend.dev"

    # Clinic info
    clinic_name: str = "Bright Smiles Dental"
    clinic_address: str = "1234 Main St, McLean, VA 22101"
    clinic_phone: str = ""
    clinic_hours_mon_fri: str = "8:00 AM - 6:00 PM"
    clinic_hours_sat: str = "9:00 AM - 2:00 PM"
    clinic_hours_sun: str = "Closed"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
