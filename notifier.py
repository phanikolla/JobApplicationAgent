import logging
import os
import markdown
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_pdf(markdown_text, output_filename):
    """
    Converts markdown text to a clean PDF using Playwright (Chromium).
    """
    logger.info(f"Generating PDF: {output_filename}")
    try:
        html_text = markdown.markdown(markdown_text)
        
        import hashlib
        
        styled_html = f"""
        <html>
        <head>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
                
                body {{
                    font-family: 'Inter', "Helvetica Neue", Helvetica, Arial, sans-serif;
                    font-size: 10.5pt;
                    line-height: 1.4;
                    color: #1a1a1a;
                    margin: 0;
                    padding: 0;
                }}
                
                h1 {{
                    font-size: 22pt;
                    font-weight: 700;
                    text-transform: uppercase;
                    text-align: center;
                    letter-spacing: 1px;
                    color: #000;
                    margin-bottom: 4px;
                    margin-top: 0;
                }}
                
                h2 {{
                    font-size: 11pt;
                    font-weight: 700;
                    text-transform: uppercase;
                    color: #000;
                    margin-top: 16px;
                    margin-bottom: 8px;
                    border-bottom: 1px solid #000;
                    padding-bottom: 2px;
                }}
                
                h3 {{
                    font-size: 11pt;
                    font-weight: 600;
                    margin-top: 8px;
                    margin-bottom: 4px;
                    color: #222;
                }}
                
                p {{
                    margin-top: 0;
                    margin-bottom: 8px;
                    text-align: justify;
                }}
                
                /* Match the contact details block directly after H1 */
                h1 + p {{
                    text-align: center;
                    font-size: 9.5pt;
                    color: #444;
                    margin-bottom: 16px;
                }}
                
                a {{
                    color: #0056b3;
                    text-decoration: none;
                }}
                
                ul {{
                    padding-left: 18px;
                    margin-top: 4px;
                    margin-bottom: 12px;
                }}
                
                li {{
                    margin-bottom: 4px;
                    text-align: left;
                }}
                
                /* Bold formatting */
                strong {{
                    font-weight: 600;
                    color: #000;
                }}
                
                em {{
                    font-style: italic;
                    color: #333;
                }}

            </style>
        </head>
        <body>
            {html_text}
        </body>
        </html>
        """
        
        # If file exists, try to remove it. If locked, create a V2 filename.
        if os.path.exists(output_filename):
            try:
                os.remove(output_filename)
            except Exception:
                base, ext = os.path.splitext(output_filename)
                import time
                timestamp = int(time.time())
                output_filename = f"{base}_{timestamp}{ext}"
                logger.warning(f"File locked, saving to alternative name: {output_filename}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content(styled_html)
            await page.pdf(
                path=output_filename, 
                format="A4", 
                margin={"top": "0.75in", "bottom": "0.75in", "left": "0.75in", "right": "0.75in"}
            )
            await browser.close()
            
        return output_filename
    except Exception as e:
        logger.error(f"Error generating PDF {output_filename}: {e}")
        return None

def send_summary_email(receiver_email, summary_markdown, attachment_paths=None):
    """
    Sends an email to the user with the summary and tailored resumes attached.
    """
    logger.info(f"Sending summary email to {receiver_email}...")
    
    sender_email = os.getenv("EMAIL_SENDER")
    app_password = os.getenv("EMAIL_APP_PASSWORD")
    
    if not sender_email or not app_password or sender_email == "pkkolla24@gmail.com" and app_password == "your_gmail_app_password_here":
        logger.warning("Email credentials not configured in .env. Skipping email dispatch.")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "Daily Agent Report: Tailored Job Applications Ready"
    
    # Convert summary to HTML
    body_html = markdown.markdown(summary_markdown)
    msg.attach(MIMEText(body_html, 'html'))
    
    # Attach files
    if attachment_paths:
        for path in attachment_paths:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                    msg.attach(part)
                except Exception as e:
                    logger.error(f"Could not attach file {path}: {e}")
            else:
                logger.warning(f"Attachment file not found: {path}")

    # Send
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, app_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        logger.info("Email sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

if __name__ == "__main__":
    generate_pdf("# Test Resume\n- Skill 1\n- Skill 2", "test_resume.pdf")
