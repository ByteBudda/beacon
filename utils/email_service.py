"""Email service stub for testing"""
class EmailService:
    def __init__(self): pass
    async def send_verification_email(self, *args, **kwargs): pass
    async def send_password_reset_email(self, *args, **kwargs): pass
    
email_service = EmailService()