import os
import smtplib
import ssl
import logging
import uuid
import time
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.utils import formatdate, make_msgid
from typing import Optional, List
from app.core.config import config

logger = logging.getLogger(__name__)


class EmailService:
    """
    Universal email service supporting:
    - SSL (port 465)
    - TLS (port 587)
    - Plain (port 25, 2525)
    - RFC 5322 compliant (Message-ID, Date, etc.)
    """
    
    def __init__(self):
        self.smtp_host = config.SMTP_HOST
        self.smtp_port = config.SMTP_PORT
        self.smtp_user = config.SMTP_USER
        self.smtp_password = config.SMTP_PASSWORD
        self.from_email = config.FROM_EMAIL or config.SMTP_USER
        self.from_name = getattr(config, 'FROM_NAME', config.APP_NAME)
        self.enabled = config.email_enabled
        self.app_name = config.APP_NAME
        self.app_url = config.APP_URL
        self.debug = config.DEBUG
        self.domain = self.from_email.split('@')[-1] if '@' in self.from_email else 'qntx.ru'
        
        # Определяем тип подключения
        self.connection_type = self._detect_connection_type()
        
        if self.enabled:
            logger.info(f"Email service initialized:")
            logger.info(f"  Host: {self.smtp_host}:{self.smtp_port}")
            logger.info(f"  User: {self.smtp_user}")
            logger.info(f"  From: {self.from_name} <{self.from_email}>")
            logger.info(f"  Domain: {self.domain}")
            logger.info(f"  Type: {self.connection_type}")
        else:
            logger.warning("Email service disabled. Check SMTP configuration in .env")

    def _detect_connection_type(self) -> str:
        """Detect connection type based on port"""
        if self.smtp_port == 465:
            return "SSL"
        elif self.smtp_port == 587:
            return "TLS"
        else:
            return "PLAIN"

    def _generate_message_id(self) -> str:
        """Generate a unique Message-ID header (RFC 5322 compliant)"""
        # Используем стандартный make_msgid из Python
        # Он создает ID в формате <timestamp.uuid@domain>
        msgid = make_msgid(domain=self.domain)
        return msgid

    def _create_message(self, to_email: str, subject: str, html_content: str,
                        text_content: Optional[str] = None) -> MIMEMultipart:
        """Create email message with all required headers (RFC 5322)"""
        msg = MIMEMultipart("alternative")
        
        # REQUIRED headers (RFC 5322)
        msg["Message-ID"] = self._generate_message_id()
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email
        msg["To"] = to_email
        msg["Reply-To"] = self.from_email
        
        # RECOMMENDED headers
        msg["X-Mailer"] = f"{self.app_name}/2.0"
        msg["X-Priority"] = "3"  # Normal priority
        msg["MIME-Version"] = "1.0"
        
        # Plain text version (fallback for old email clients)
        if text_content:
            text_part = MIMEText(text_content, "plain", "utf-8")
            msg.attach(text_part)
        
        # HTML version
        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)
        
        # Log the Message-ID for debugging
        logger.debug(f"Generated Message-ID: {msg['Message-ID']}")
        
        return msg

    def _send_email(self, to_email: str, subject: str, html_content: str,
                   text_content: Optional[str] = None, attachments: Optional[List[str]] = None) -> bool:
        """Send email using appropriate connection method"""
        if not self.enabled:
            logger.warning(f"Email disabled. Would send to {to_email}: {subject}")
            if self.debug:
                self._print_debug_email(to_email, subject, html_content)
            return True

        try:
            # Create message
            msg = self._create_message(to_email, subject, html_content, text_content)
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    self._attach_file(msg, file_path)
            
            # Send based on connection type
            if self.connection_type == "SSL":
                return self._send_via_ssl(msg, to_email)
            elif self.connection_type == "TLS":
                return self._send_via_tls(msg, to_email)
            else:
                return self._send_via_plain(msg, to_email)
                
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    def _send_via_ssl(self, msg: MIMEMultipart, to_email: str) -> bool:
        """Send via SSL (port 465)"""
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                server.set_debuglevel(1 if self.debug else 0)
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
                logger.info(f"Email sent via SSL to {to_email}")
                logger.debug(f"Message-ID: {msg['Message-ID']}")
                return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            logger.error(f"Check username: {self.smtp_user} and password")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    def _send_via_tls(self, msg: MIMEMultipart, to_email: str) -> bool:
        """Send via TLS (port 587)"""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.set_debuglevel(1 if self.debug else 0)
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
                logger.info(f"Email sent via TLS to {to_email}")
                logger.debug(f"Message-ID: {msg['Message-ID']}")
                return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    def _send_via_plain(self, msg: MIMEMultipart, to_email: str) -> bool:
        """Send via plain connection (port 25, 2525, etc.)"""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.set_debuglevel(1 if self.debug else 0)
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
                logger.info(f"Email sent via plain to {to_email}")
                logger.debug(f"Message-ID: {msg['Message-ID']}")
                return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """Attach file to email"""
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
                file_name = Path(file_path).name
                
                # Determine file type
                if file_path.endswith('.png'):
                    attachment = MIMEImage(file_data, _subtype='png')
                elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                    attachment = MIMEImage(file_data, _subtype='jpeg')
                elif file_path.endswith('.gif'):
                    attachment = MIMEImage(file_data, _subtype='gif')
                else:
                    attachment = MIMEText(file_data, _subtype='octet-stream')
                
                attachment.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
                attachment.add_header('Content-ID', f'<{file_name}>')
                msg.attach(attachment)
                logger.debug(f"Attached file: {file_name}")
        except Exception as e:
            logger.warning(f"Failed to attach file {file_path}: {e}")

    def _print_debug_email(self, to_email: str, subject: str, html_content: str) -> None:
        """Print email content for debugging"""
        msgid = self._generate_message_id()
        print(f"\n{'='*80}")
        print(f"📧 EMAIL (DEBUG MODE - NOT SENT)")
        print(f"{'='*80}")
        print(f"Message-ID: {msgid}")
        print(f"Date: {formatdate(localtime=True)}")
        print(f"From: {self.from_name} <{self.from_email}>")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"{'='*80}")
        print(f"Content:")
        print(html_content[:1000] + "..." if len(html_content) > 1000 else html_content)
        print(f"{'='*80}\n")

    def send_verification_email(self, to_email: str, verification_link: str) -> bool:
        """Send email verification link"""
        subject = f"Verify Your Email - {self.app_name}"
        
        text_content = f"""
Welcome to {self.app_name}!

Please verify your email address by clicking the link below:

{verification_link}

This link will expire in 24 hours.

If you didn't create an account, you can safely ignore this email.

---
{self.app_name} - URL Shortener with Analytics
{self.app_url}
Questions? Contact us at {self.from_email}
        """
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify Your Email - {self.app_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            color: white;
            margin: 0;
            font-size: 32px;
            font-weight: 700;
        }}
        .header p {{
            color: rgba(255,255,255,0.9);
            margin-top: 10px;
            font-size: 14px;
        }}
        .content {{
            padding: 40px 30px;
            background: white;
        }}
        .content h2 {{
            color: #333;
            font-size: 24px;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        .content p {{
            color: #666;
            margin-bottom: 20px;
            line-height: 1.6;
        }}
        .button {{
            display: inline-block;
            padding: 14px 32px;
            background: #0078d4;
            color: white !important;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
            transition: all 0.2s ease;
        }}
        .button:hover {{
            background: #006abc;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,120,212,0.3);
        }}
        .link {{
            background: #f8f9fa;
            padding: 12px 16px;
            border-radius: 8px;
            word-break: break-all;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            margin: 16px 0;
            border: 1px solid #e9ecef;
        }}
        .warning {{
            color: #f5a623;
            font-size: 12px;
            margin-top: 20px;
            padding: 12px;
            background: #fff8e7;
            border-radius: 8px;
            border-left: 3px solid #f5a623;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            font-size: 12px;
            color: #999;
            border-top: 1px solid #eee;
            background: #fafafa;
        }}
        .footer a {{
            color: #0078d4;
            text-decoration: none;
        }}
        .footer a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.app_name}</h1>
            <p>URL Shortener with Analytics</p>
        </div>
        <div class="content">
            <h2>Verify Your Email Address</h2>
            <p>Thanks for signing up! Please click the button below to verify your email address and activate your account.</p>
            
            <div style="text-align: center;">
                <a href="{verification_link}" class="button">Verify Email Address</a>
            </div>
            
            <p>Or copy and paste this link into your browser:</p>
            <div class="link">{verification_link}</div>
            
            <div class="warning">
                ⚠️ This link will expire in 24 hours.
            </div>
            
            <p>If you didn't create an account, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>&copy; 2024 {self.app_name}. All rights reserved.</p>
            <p><a href="{self.app_url}">{self.app_url}</a> | <a href="mailto:{self.from_email}">Contact Support</a></p>
        </div>
    </div>
</body>
</html>
        """
        
        return self._send_email(to_email, subject, html_content, text_content)

    def send_password_reset_email(self, to_email: str, reset_link: str) -> bool:
        """Send password reset link"""
        subject = f"Reset Your Password - {self.app_name}"
        
        text_content = f"""
Password Reset Request

We received a request to reset your password. Click the link below to create a new password:

{reset_link}

This link will expire in 1 hour.

If you didn't request this, you can safely ignore this email.

---
{self.app_name} - URL Shortener with Analytics
{self.app_url}
Questions? Contact us at {self.from_email}
        """
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your Password - {self.app_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            color: white;
            margin: 0;
            font-size: 32px;
            font-weight: 700;
        }}
        .content {{
            padding: 40px 30px;
            background: white;
        }}
        .content h2 {{
            color: #333;
            font-size: 24px;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        .content p {{
            color: #666;
            margin-bottom: 20px;
            line-height: 1.6;
        }}
        .button {{
            display: inline-block;
            padding: 14px 32px;
            background: #f5576c;
            color: white !important;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
            transition: all 0.2s ease;
        }}
        .button:hover {{
            background: #e8455a;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(245,87,108,0.3);
        }}
        .link {{
            background: #f8f9fa;
            padding: 12px 16px;
            border-radius: 8px;
            word-break: break-all;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            margin: 16px 0;
            border: 1px solid #e9ecef;
        }}
        .warning {{
            color: #f5a623;
            font-size: 12px;
            margin-top: 20px;
            padding: 12px;
            background: #fff8e7;
            border-radius: 8px;
            border-left: 3px solid #f5a623;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            font-size: 12px;
            color: #999;
            border-top: 1px solid #eee;
            background: #fafafa;
        }}
        .footer a {{
            color: #f5576c;
            text-decoration: none;
        }}
        .footer a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{self.app_name}</h1>
        </div>
        <div class="content">
            <h2>Reset Your Password</h2>
            <p>We received a request to reset your password. Click the button below to create a new password.</p>
            
            <div style="text-align: center;">
                <a href="{reset_link}" class="button">Reset Password</a>
            </div>
            
            <p>Or copy and paste this link into your browser:</p>
            <div class="link">{reset_link}</div>
            
            <div class="warning">
                ⚠️ This link will expire in 1 hour.
            </div>
            
            <p>If you didn't request this, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>&copy; 2024 {self.app_name}. All rights reserved.</p>
            <p><a href="{self.app_url}">{self.app_url}</a> | <a href="mailto:{self.from_email}">Contact Support</a></p>
        </div>
    </div>
</body>
</html>
        """
        
        return self._send_email(to_email, subject, html_content, text_content)

    def send_welcome_email(self, to_email: str, username: str) -> bool:
        """Send welcome email after verification"""
        subject = f"Welcome to {self.app_name}, {username}! 🎉"
        
        text_content = f"""
Welcome to {self.app_name}!

Hi {username},

Your email has been verified successfully! You're now ready to start shortening links and tracking analytics.

Here's what you can do:
• Create short, memorable links
• Track clicks and analytics
• Generate QR codes
• Password protect your links
• Set link expiration dates

Get started now: {self.app_url}

---
{self.app_name} - URL Shortener with Analytics
Questions? Contact us at {self.from_email}
        """
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to {self.app_name}!</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 40px auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            color: white;
            margin: 0;
            font-size: 32px;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .content h2 {{
            color: #333;
            font-size: 24px;
            margin-bottom: 20px;
        }}
        .content h3 {{
            color: #555;
            font-size: 18px;
            margin: 20px 0 10px;
        }}
        .feature-list {{
            margin: 20px 0;
            padding-left: 20px;
            list-style: none;
        }}
        .feature-list li {{
            margin: 12px 0;
            color: #666;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .feature-list li::before {{
            content: "✓";
            color: #0078d4;
            font-weight: bold;
            font-size: 18px;
        }}
        .button {{
            display: inline-block;
            padding: 14px 32px;
            background: #0078d4;
            color: white !important;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
            transition: all 0.2s;
        }}
        .button:hover {{
            background: #006abc;
            transform: translateY(-2px);
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            font-size: 12px;
            color: #999;
            border-top: 1px solid #eee;
            background: #fafafa;
        }}
        .footer a {{
            color: #0078d4;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to {self.app_name}! 🚀</h1>
        </div>
        <div class="content">
            <h2>Hi {username}!</h2>
            <p>Your email has been verified successfully! You're now ready to start shortening links and tracking analytics.</p>
            
            <h3>Here's what you can do:</h3>
            <ul class="feature-list">
                <li>🔗 Create short, memorable links</li>
                <li>📊 Track clicks and analytics</li>
                <li>📱 Generate QR codes</li>
                <li>🔒 Password protect your links</li>
                <li>⏰ Set link expiration dates</li>
                <li>📈 View detailed statistics</li>
            </ul>
            
            <div style="text-align: center;">
                <a href="{self.app_url}" class="button">Go to Dashboard</a>
            </div>
        </div>
        <div class="footer">
            <p>&copy; 2024 {self.app_name}. All rights reserved.</p>
            <p><a href="{self.app_url}">{self.app_url}</a></p>
        </div>
    </div>
</body>
</html>
        """
        
        return self._send_email(to_email, subject, html_content, text_content)


# Create singleton instance
email_service = EmailService()