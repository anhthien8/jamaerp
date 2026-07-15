"""JAMA HOME CRM Telegram Bot — aiogram 3.x entry point."""

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from bot.handlers import (
    start,
    lead_intake,
    pipeline,
    briefing,
    site_report,
    material_request,
    incident,
    checkin_out,
    group_utils,
    feedback,
    hr,
)

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        sys.exit(1)

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Register handlers
    dp.include_router(group_utils.router)  # /id + group welcome (trước để ưu tiên)
    dp.include_router(start.router)
    dp.include_router(lead_intake.router)
    dp.include_router(pipeline.router)
    dp.include_router(briefing.router)
    dp.include_router(site_report.router)
    dp.include_router(material_request.router)
    dp.include_router(incident.router)
    dp.include_router(checkin_out.router)
    dp.include_router(feedback.router)
    dp.include_router(hr.router)

    logger.info("🚀 JAMA HOME CRM Bot starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
