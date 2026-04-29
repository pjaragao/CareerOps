import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)

def send_email(to_email: str, subject: str, body: str, attachment_path: str = None):
    """
    Envia um e-mail via SMTP com anexo opcional.
    Configurações devem estar no .env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    
    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning("Configurações SMTP ausentes. E-mail não enviado.")
        print("⚠️ Configurações SMTP ausentes. E-mail não enviado.")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
                msg.attach(part)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        logger.info(f"E-mail enviado com sucesso para {to_email}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar e-mail: {e}")
        return False
