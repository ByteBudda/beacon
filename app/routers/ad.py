import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse

from app.services.ad_service import ad_service
from app.core.config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["ad"])


@router.get("/ad")
async def get_ad(request: Request):
    """Get ad HTML for embedding via iframe"""
    db = request.app.state.db
    
    # Check if ads are enabled
    enabled = await ad_service.get(db, "ad_enabled", "false")
    if enabled != "true":
        return {"ad_html": "", "enabled": False}
    
    ad_html = await ad_service.get_ad_html(db)
    delay = await ad_service.get_delay(db)
    ad_title = await ad_service.get(db, "ad_title", "Реклама")
    skip_text = await ad_service.get(db, "ad_skip_text", "Перейти к сайту")
    
    # Process HTML - convert iframe src to srcdoc for local execution
    processed_ad = ""
    if ad_html:
        import re
        import html as html_escape
        if '<iframe' in ad_html:
            def convert_iframe(match):
                iframe = match.group(0)
                src_match = re.search(r'src=["\']([^"\']+)["\']', iframe)
                if src_match:
                    src = src_match.group(1)
                    new_iframe = iframe.replace(f'src="{src}"', '').replace(f"src='{src}'", '')
                    new_iframe = new_iframe.replace('>', f' srcdoc="{html_escape.escape(src)}">')
                    return new_iframe
                return iframe
            processed_ad = re.sub(r'<iframe[^>]*>', convert_iframe, ad_html)
        else:
            processed_ad = ad_html
    
    return {
        "ad_html": processed_ad,
        "delay": delay,
        "title": ad_title,
        "skip_text": skip_text,
        "enabled": True
    }


@router.get("/ad/iframe")
async def get_ad_iframe(request: Request):
    """Get ad as standalone HTML page for iframe embedding"""
    db = request.app.state.db
    
    enabled = await ad_service.get(db, "ad_enabled", "false")
    if enabled != "true":
        return HTMLResponse('<div style="text-align:center;padding:20px;color:#666">Реклама отключена</div>')
    
    ad_html = await ad_service.get_ad_html(db)
    delay = await ad_service.get_delay(db)
    skip_text = await ad_service.get(db, "ad_skip_text", "Перейти к сайту")
    
    # Process HTML - just pass through as-is, browser will render it
    processed_ad = ad_html
    
    return HTMLResponse(f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#1a1a2e;color:#fff;padding:10px}}
.ad-content{{width:100%;max-width:300px;text-align:center}}
.ad-content iframe{{border:none;border-radius:4px;max-width:100%;width:100%}}
.timer{{font-size:24px;font-weight:700;color:#0078d4;margin:10px 0}}
.btn-skip{{display:inline-block;padding:8px 20px;background:#0078d4;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer;text-decoration:none}}
.btn-skip:hover{{background:#006abc}}
</style>
</head>
<body>
<div class="ad-content">
<div class="ad-content">
{processed_ad}
</div>
<div class="timer" id="timer">{delay}</div>
<a class="btn-skip" id="btn-skip" href="#">{skip_text}</a>
</div>
<script>
let timer={delay};
const el=document.getElementById('timer');
const btn=document.getElementById('btn-skip');
const interval=setInterval(()=>{{
timer--;
el.textContent=timer;
if(timer<=0){{
clearInterval(interval);
btn.style.opacity='1';
}}
}},1000);
</script>
</body>
</html>''')