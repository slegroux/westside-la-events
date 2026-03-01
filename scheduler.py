#!/usr/bin/env python3
"""
Background scheduler for periodic event scraping.
Runs scrapers on a schedule to keep the database fresh.
"""
import time
import schedule
from datetime import datetime
import logging
import config

# Import the scraper runner
from run_scrapers import main as run_all_scrapers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _cron_to_daily_time(cron_expr: str) -> str:
    """
    Convert a 5-field cron expression to schedule's HH:MM format.

    Supports daily cron expressions with fixed minute and hour:
    - "0 3 * * *" -> "03:00"

    Falls back to "02:00" for unsupported expressions.
    """
    fallback = "02:00"
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return fallback

    minute, hour, day, month, weekday = parts
    if day != "*" or month != "*" or weekday != "*":
        return fallback
    if not minute.isdigit() or not hour.isdigit():
        return fallback

    minute_i = int(minute)
    hour_i = int(hour)
    if minute_i < 0 or minute_i > 59 or hour_i < 0 or hour_i > 23:
        return fallback

    return f"{hour_i:02d}:{minute_i:02d}"


def scheduled_scrape():
    """Run all scrapers on schedule."""
    logger.info("=" * 60)
    logger.info("Starting scheduled scrape")
    logger.info("=" * 60)

    try:
        run_all_scrapers()
        logger.info("Scheduled scrape completed successfully")
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}", exc_info=True)


def main():
    """Set up and run the scheduler."""
    schedule_time = _cron_to_daily_time(config.SCRAPER_SCHEDULE)

    logger.info("Event Scraper Scheduler Starting...")
    logger.info(f"Configured cron: {config.SCRAPER_SCHEDULE}")
    logger.info(f"Schedule: Daily at {schedule_time}")

    # Schedule scraping daily based on SCRAPER_SCHEDULE.
    schedule.every().day.at(schedule_time).do(scheduled_scrape)

    # Optional: Also run every 6 hours for more frequent updates
    # schedule.every(6).hours.do(scheduled_scrape)

    # Run once immediately on startup
    logger.info("Running initial scrape...")
    scheduled_scrape()

    logger.info("Scheduler initialized. Waiting for scheduled tasks...")

    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")


if __name__ == '__main__':
    main()
