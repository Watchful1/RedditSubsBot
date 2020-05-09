#!/usr/bin/python3

import logging.handlers
import sys
import signal
import time
import traceback
import discord_logging
import argparse

log = discord_logging.init_logging(
	backup_count=20
)


from database import Database
import static
import reddit_class
import messages
import comments
import subreddits
import notifications
import utils
import stats


database = None


def signal_handler(signal, frame):
	log.info("Handling interrupt")
	database.close()
	discord_logging.flush_discord()
	sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Reddit UpdateMe bot")
	parser.add_argument("user", help="The reddit user account to use")
	parser.add_argument("--once", help="Only run the loop once", action='store_const', const=True, default=False)
	parser.add_argument("--debug_db", help="Use the debug database", action='store_const', const=True, default=False)
	parser.add_argument(
		"--no_post", help="Print out reddit actions instead of posting to reddit", action='store_const', const=True,
		default=False)
	parser.add_argument(
		"--no_backup", help="Don't backup the database", action='store_const', const=True, default=False)
	parser.add_argument(
		"--reset_comment", help="Reset the last comment read timestamp", action='store_const', const=True,
		default=False)
	parser.add_argument("--debug", help="Set the log level to debug", action='store_const', const=True, default=False)
	args = parser.parse_args()

	if args.debug:
		discord_logging.set_level(logging.DEBUG)

	# discord_logging.init_discord_logging(args.user, logging.WARNING, 1)
	static.ACCOUNT_NAME = args.user
	reddit_message = reddit_class.Reddit(args.user, "message", args.no_post)
	reddit_search = reddit_class.Reddit(args.user, "search", args.no_post)
	database = Database(debug=args.debug_db)
	if args.reset_comment:
		log.info("Resetting comment processed timestamp")
		database.save_datetime("comment_timestamp", utils.datetime_now())

	last_backup = None
	last_comments = None
	while True:
		startTime = time.perf_counter()
		log.debug("Starting run")

		actions = 0
		errors = 0

		try:
			actions += messages.process_messages(reddit_message, database)
		except Exception as err:
			log.warning(f"Error processing messages: {err}")
			log.warning(traceback.format_exc())
			errors += 1

		try:
			actions += comments.process_comments(reddit_message, database)
		except Exception as err:
			log.warning(f"Error processing comments: {err}")
			log.warning(traceback.format_exc())
			errors += 1

		try:
			subreddits.scan_subreddits(reddit_search, database)
		except Exception as err:
			log.warning(f"Error scanning subreddits: {err}")
			log.warning(traceback.format_exc())
			errors += 1

		try:
			actions += notifications.send_queued_notifications(reddit_message, database)
		except Exception as err:
			log.warning(f"Error sending notifications: {err}")
			log.warning(traceback.format_exc())
			errors += 1

		if utils.time_offset(last_comments, minutes=30):
			try:
				actions += comments.update_comments(reddit_message, database)
				last_comments = utils.datetime_now()
			except Exception as err:
				log.warning(f"Error updating comments: {err}")
				log.warning(traceback.format_exc())
				errors += 1

		latest_stats = database.get_datetime("stats_day", is_date=True)
		current_day = utils.date_now()
		if latest_stats is None:
			database.save_datetime("stats_day", current_day)
		elif latest_stats != current_day:
			log.info(f"Saving stats for day {current_day.strftime('%Y-%m-%d')}")
			stats.save_stats_for_day(database, latest_stats)
			database.save_datetime("stats_day", current_day)

		if not args.no_backup and utils.time_offset(last_backup, hours=4):
			try:
				database.backup()
				last_backup = utils.datetime_now()

				database.clean()
			except Exception as err:
				log.warning(f"Error backing up database: {err}")
				log.warning(traceback.format_exc())
				errors += 1

		log.debug(f"Run complete after: {int(time.perf_counter() - startTime)}")

		discord_logging.flush_discord()
		database.commit()

		if args.once:
			break

		sleep_time = max(30 - actions, 0) + (30 * errors)
		log.debug(f"Sleeping {sleep_time}")

		time.sleep(sleep_time)
