#!/usr/bin/env python3
"""
Background scheduler for periodic event scraping.
Runs scrapers on a schedule to keep the database fresh.
"""
import time
import schedule
from datetime import datetime
import logging

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
    logger.info("Event Scraper Scheduler Starting...")
    logger.info("Schedule: Daily at 2:00 AM")

    # Schedule scraping daily at 2 AM (when traffic is low)
    schedule.every().day.at("02:00").do(scheduled_scrape)

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
