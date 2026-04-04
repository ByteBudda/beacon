"""Analytics stub for testing"""
class Analytics:
    async def track_click(self, *args, **kwargs): pass
    async def get_stats(self, *args, **kwargs): return {}

analytics = Analytics()