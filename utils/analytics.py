import logging
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

import user_agents

logger = logging.getLogger(__name__)


class Analytics:
    """Analytics processor for link clicks"""
    
    def process_click(self, ip: str, user_agent: str, referer: str) -> dict:
        """
        Process click data and return structured analytics
        
        Args:
            ip: Client IP address
            user_agent: User agent string
            referer: Referer URL
            
        Returns:
            Dictionary with processed analytics data
        """
        ua = user_agents.parse(user_agent) if user_agent else None
        
        # Device type detection
        if ua:
            if ua.is_mobile:
                device_type = "mobile"
            elif ua.is_tablet:
                device_type = "tablet"
            elif ua.is_pc:
                device_type = "desktop"
            else:
                device_type = "unknown"
            
            # OS detection
            if ua.os.family:
                os_name = ua.os.family
            else:
                os_name = "unknown"
            
            # Browser detection
            if ua.browser.family:
                browser = ua.browser.family
            else:
                browser = "unknown"
        else:
            device_type = "unknown"
            os_name = "unknown"
            browser = "unknown"
        
        # Clean referer
        if not referer or referer == "":
            referer = "direct"
        else:
            # Extract domain from referer
            try:
                parsed = urlparse(referer)
                if parsed.netloc:
                    referer = parsed.netloc
                else:
                    referer = referer.split('/')[2] if '://' in referer else referer
            except:
                pass
        
        return {
            "ip": ip[:45] if ip else "unknown",
            "device_type": device_type,
            "os": os_name,
            "browser": browser,
            "referer": referer[:255] if referer else "direct",
            "user_agent": user_agent[:500] if user_agent else "",
            "timestamp": datetime.utcnow()
        }
    
    async def get_aggregated_stats(self, clicks: List[dict]) -> dict:
        """
        Aggregate click statistics
        
        Args:
            clicks: List of click data dictionaries
            
        Returns:
            Dictionary with aggregated statistics
        """
        if not clicks:
            return {
                "total_clicks": 0,
                "clicks_by_device": {},
                "clicks_by_browser": {},
                "clicks_by_os": {},
                "top_referrers": {}
            }
        
        stats = {
            "total_clicks": len(clicks),
            "clicks_by_device": {},
            "clicks_by_browser": {},
            "clicks_by_os": {},
            "top_referrers": {}
        }
        
        for click in clicks:
            # Device stats
            device = click.get("device_type", "unknown")
            stats["clicks_by_device"][device] = stats["clicks_by_device"].get(device, 0) + 1
            
            # Browser stats
            browser = click.get("browser", "unknown")
            if browser:
                browser = browser.split()[0]  # Get first part (e.g., "Chrome" from "Chrome 120")
            stats["clicks_by_browser"][browser] = stats["clicks_by_browser"].get(browser, 0) + 1
            
            # OS stats
            os_name = click.get("os", "unknown")
            stats["clicks_by_os"][os_name] = stats["clicks_by_os"].get(os_name, 0) + 1
            
            # Referrer stats
            referer = click.get("referer", "direct")
            if referer:
                # Clean up referer
                if referer.startswith(('http://', 'https://')):
                    referer = urlparse(referer).netloc or referer
                stats["top_referrers"][referer] = stats["top_referrers"].get(referer, 0) + 1
        
        # Sort referrers by count and limit to top 10
        stats["top_referrers"] = dict(sorted(
            stats["top_referrers"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10])
        
        return stats
    
    def get_clicks_by_timeframe(self, clicks: List[dict], days: int = 7) -> dict:
        """
        Group clicks by time (daily)
        
        Args:
            clicks: List of click data dictionaries
            days: Number of days to analyze
            
        Returns:
            Dictionary with daily click counts
        """
        from datetime import timedelta
        
        result = {}
        now = datetime.utcnow()
        
        for i in range(days):
            date = now - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            result[date_str] = 0
        
        for click in clicks:
            ts = click.get("timestamp", click.get("ts"))
            if isinstance(ts, (int, float)):
                date = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            elif isinstance(ts, datetime):
                date = ts.strftime('%Y-%m-%d')
            else:
                continue
            
            if date in result:
                result[date] += 1
        
        # Sort by date
        return dict(sorted(result.items()))
    
    def get_geolocation_stats(self, clicks: List[dict]) -> dict:
        """
        Get geolocation statistics from IP addresses
        
        Note: Requires additional IP geolocation service integration
        """
        # Placeholder for future implementation
        return {"countries": {}, "cities": {}}
    
    def get_hourly_distribution(self, clicks: List[dict]) -> dict:
        """
        Get hourly distribution of clicks
        
        Args:
            clicks: List of click data dictionaries
            
        Returns:
            Dictionary with hour as key and click count as value
        """
        hourly = {str(i).zfill(2): 0 for i in range(24)}
        
        for click in clicks:
            ts = click.get("timestamp", click.get("ts"))
            if isinstance(ts, (int, float)):
                hour = datetime.fromtimestamp(ts).strftime('%H')
            elif isinstance(ts, datetime):
                hour = ts.strftime('%H')
            else:
                continue
            
            hourly[hour] = hourly.get(hour, 0) + 1
        
        return hourly


# Create singleton instance
analytics = Analytics()