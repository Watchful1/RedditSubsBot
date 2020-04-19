import discord_logging

log = discord_logging.get_logger(init=True)


import reddit_test
import notifications
import utils
from classes.subscription import Subscription
from classes.submission import Submission
from classes.notification import Notification


def queue_message(database, subscriber_name, author_name, subreddit_name, submission_id, recurring=True):
	subscriber = database.get_or_add_user(subscriber_name)
	author = database.get_or_add_user(author_name)
	subreddit = database.get_or_add_subreddit(subreddit_name)
	subscription = database.get_subscription_by_fields(subscriber, author, subreddit)
	if subscription is None:
		subscription = Subscription(
			subscriber=subscriber,
			author=author,
			subreddit=subreddit,
			recurring=recurring
		)
		database.add_subscription(subscription)
	submission = database.get_submission_by_id(submission_id)
	if submission is None:
		submission = Submission(
			submission_id=submission_id,
			time_created=utils.datetime_now(),
			author_name=author_name,
			subreddit=subreddit,
			permalink=f"/r/{subreddit_name}/comments/{submission_id}/"
		)
		database.add_submission(submission)
	database.add_notification(Notification(subscription, submission))
	database.commit()


def assert_message(message, dest_username, contains):
	assert message.dest.name == dest_username
	for contain in contains:
		assert contain in message.body


def test_send_message(database, reddit):
	submission_id = utils.random_id()
	queue_message(database, "Subscriber1", "Author1", "Subreddit1", submission_id)

	assert database.get_count_pending_notifications() == 1
	notifications.send_queued_notifications(reddit, database)
	assert database.get_count_pending_notifications() == 0
	assert len(database.get_user_subscriptions_by_name("Subscriber1")) == 1

	assert len(reddit.sent_messages) == 1
	assert_message(
		reddit.sent_messages[0], "Subscriber1", ["u/Author1", "r/Subreddit1", "remove your subscription", submission_id])


def test_send_message_update(database, reddit):
	submission_id = utils.random_id()
	queue_message(database, "Subscriber1", "Author1", "Subreddit1", submission_id, False)

	assert database.get_count_pending_notifications() == 1
	notifications.send_queued_notifications(reddit, database)
	assert database.get_count_pending_notifications() == 0
	assert len(database.get_user_subscriptions_by_name("Subscriber1")) == 0

	assert len(reddit.sent_messages) == 1
	assert_message(
		reddit.sent_messages[0], "Subscriber1",
		[
			"u/Author1", "r/Subreddit1", "if you want to be messaged the next", "if you want to be messaged every",
			submission_id
		])


def test_send_messages(database, reddit):
	submission_id1 = utils.random_id()
	submission_id2 = utils.random_id()
	submission_id3 = utils.random_id()
	queue_message(database, "Subscriber1", "Author1", "Subreddit1", submission_id1)
	queue_message(database, "Subscriber2", "Author1", "Subreddit1", submission_id1)
	queue_message(database, "Subscriber1", "Author2", "Subreddit1", submission_id2)
	queue_message(database, "Subscriber3", "Author2", "Subreddit1", submission_id2)
	queue_message(database, "Subscriber2", "Author1", "Subreddit2", submission_id3)
	queue_message(database, "Subscriber3", "Author1", "Subreddit2", submission_id3)

	assert database.get_count_pending_notifications() == 6
	notifications.send_queued_notifications(reddit, database)
	assert database.get_count_pending_notifications() == 0

	assert len(reddit.sent_messages) == 6
	assert_message(reddit.sent_messages[0], "Subscriber1", ["u/Author1", "r/Subreddit1", submission_id1])
	assert_message(reddit.sent_messages[1], "Subscriber2", ["u/Author1", "r/Subreddit1", submission_id1])
	assert_message(reddit.sent_messages[2], "Subscriber1", ["u/Author2", "r/Subreddit1", submission_id2])
	assert_message(reddit.sent_messages[3], "Subscriber3", ["u/Author2", "r/Subreddit1", submission_id2])
	assert_message(reddit.sent_messages[4], "Subscriber2", ["u/Author1", "r/Subreddit2", submission_id3])
	assert_message(reddit.sent_messages[5], "Subscriber3", ["u/Author1", "r/Subreddit2", submission_id3])