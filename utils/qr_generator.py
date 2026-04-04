import base64
import io
import logging
from typing import Optional

import qrcode
from PIL import Image

from app.core.config import config

logger = logging.getLogger(__name__)


class QRGenerator:
    """QR code generator for short links"""
    
    def __init__(self):
        self.box_size = config.QR_CODE_SIZE
        self.border = config.QR_CODE_BORDER
        
    def generate_qr_code(self, slug: str, custom_domain: Optional[str] = None, 
                     fill_color: str = "000000", back_color: str = "ffffff") -> Optional[str]:
        """
        Generate QR code as base64 string
        
        Args:
            slug: Link slug
            custom_domain: Optional custom domain
            fill_color: QR code fill color hex (default: 000000)
            back_color: QR code background color hex (default: ffffff)
            
        Returns:
            Base64 encoded PNG image or None if failed
        """
        try:
            # Build URL
            if custom_domain:
                url = f"http://{custom_domain}/s/{slug}"
            else:
                url = f"{config.APP_URL}/s/{slug}"
            
            # Ensure colors are 6-char hex without #
            fill = str(fill_color).lstrip('#') or "000000"
            back = str(back_color).lstrip('#') or "ffffff"
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=self.box_size,
                border=self.border,
            )
            qr.add_data(url)
            qr.make(fit=True)
            
            # Create image with custom colors (pillow uses RGB hex without #)
            img = qr.make_image(fill_color=f"#{fill}", back_color=f"#{back}")
            
            # Convert to base64
            buffered = io.BytesIO()
            img.save(buffered, format="PNG", optimize=True)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            logger.debug(f"QR code generated for {slug}")
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Failed to generate QR code for {slug}: {e}")
            return None
    
    def generate_qr_code_with_logo(self, slug: str, logo_path: Optional[str] = None) -> Optional[str]:
        """
        Generate QR code with logo in center
        
        Args:
            slug: Link slug
            logo_path: Path to logo image file
            
        Returns:
            Base64 encoded PNG image or None if failed
        """
        try:
            url = f"{config.APP_URL}/s/{slug}"
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=3,
                error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction for logo
                box_size=self.box_size,
                border=self.border,
            )
            qr.add_data(url)
            qr.make(fit=True)
            
            # Create QR code image
            qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
            
            # Add logo if provided
            if logo_path:
                try:
                    logo = Image.open(logo_path)
                    
                    # Calculate logo size (30% of QR code)
                    logo_size = int(min(qr_img.size) * 0.3)
                    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                    
                    # Calculate position
                    pos = ((qr_img.size[0] - logo_size) // 2,
                           (qr_img.size[1] - logo_size) // 2)
                    
                    # Paste logo
                    qr_img.paste(logo, pos, logo if logo.mode == 'RGBA' else None)
                    
                except Exception as e:
                    logger.warning(f"Failed to add logo to QR code: {e}")
            
            # Convert to base64
            buffered = io.BytesIO()
            qr_img.save(buffered, format="PNG", optimize=True)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            logger.debug(f"QR code with logo generated for {slug}")
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            logger.error(f"Failed to generate QR code with logo for {slug}: {e}")
            return None
    
    def generate_multiple_qr_codes(self, links: list) -> dict:
        """
        Generate QR codes for multiple links
        
        Args:
            links: List of link dicts with 'slug' and 'custom_domain' keys
            
        Returns:
            Dictionary with slug as key and QR code base64 as value
        """
        results = {}
        for link in links:
            slug = link.get('slug')
            if slug:
                custom_domain = link.get('custom_domain')
                qr_code = self.generate_qr_code(slug, custom_domain)
                if qr_code:
                    results[slug] = qr_code
        return results


# Create singleton instance
qr_generator = QRGenerator()