"""QR code generator stub for testing"""
import base64

class QRGenerator:
    def generate(self, data: str) -> str:
        """Generate QR code - returns base64 encoded image"""
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    def generate_svg(self, data: str) -> str:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect fill="#000" width="100" height="100"/></svg>'

qr_generator = QRGenerator()