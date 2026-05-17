from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # VAPI
    vapi_api_key: str
    vapi_phone_number_id: str = ""
    server_base_url: str = "https://placeholder.ngrok.io"

    # Google Calendar (optional — set to 'skip' to use local mock)
    google_calendar_id: str = "skip"
    google_service_account_json: str = "./credentials/google-service-account.json"

    # Email (Gmail SMTP)
    clinic_owner_email: str = "khannn762@gmail.com"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str = "naseebullah700000@gmail.com"
    smtp_password: str = ""
    from_email: str = "naseebullah700000@gmail.com"

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
