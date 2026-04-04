"""Beacon URL Shortener - Entry Point"""
from app.main import app

if __name__ == "__main__":
    import uvicorn
    from app.core.config import config
    from app.core.logging import setup_logging

    setup_logging(config.LOG_LEVEL, config.LOG_FORMAT)
    warnings = config.validate()
    for w in warnings:
        print(f"WARNING: {w}")

    uvicorn.run("app.main:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=config.DEBUG)
