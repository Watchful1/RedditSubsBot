import praw
import OAuth2Util
import time
from datetime import datetime
import database
import logging
import logging.handlers
import os
import strings
import re
import globals


### Constants ###
# column numbers
ID_NUM = 0
SUBSCRIBER_NUM = 1
SUBSCRIBEDTO_NUM = 2
SUBREDDIT_NUM = 3
LASTCHECKED_NUM = 4


### Logging setup ###
LOG_LEVEL = logging.DEBUG
LOG_FOLDER = "logs"
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)
LOG_FILENAME = LOG_FOLDER+"/"+"bot.log"
LOG_FILE_BACKUPCOUNT = 5
LOG_FILE_MAXSIZE = 1024 * 256

log = logging.getLogger("bot")
log.setLevel(LOG_LEVEL)
log_formatter = logging.Formatter('%(levelname)s: %(message)s')
log_stderrHandler = logging.StreamHandler()
log_stderrHandler.setFormatter(log_formatter)
log.addHandler(log_stderrHandler)
if LOG_FILENAME is not None:
	log_fileHandler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=LOG_FILE_MAXSIZE, backupCount=LOG_FILE_BACKUPCOUNT)
	log_formatter_file = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
	log_fileHandler.setFormatter(log_formatter_file)
	log.addHandler(log_fileHandler)


### Functions ###

def searchSubreddit(subreddit, authorHash, oldestTimestamp):
	if authorHash == {}: return
	oldestSeconds = time.mktime(datetime.strptime(oldestTimestamp, "%Y-%m-%d %H:%M:%S").timetuple())
	log.debug("Getting posts in %s newer than %s", subreddit, oldestTimestamp)

	# retrieving submissions takes some time, but starts with the newest first
	# so we want to cache the time we start, but don't reset the timestamps until we know we aren't going to crash
	# better to send two notifications than none
	startTimestamp = datetime.now()
	for post in praw.helpers.submissions_between(r, subreddit, oldestSeconds, verbosity=0):
		log.debug("Found post by /u/"+str(post.author).lower())
		author = str(post.author).lower()
		if author in authorHash:
			for key in authorHash[author]:
				if datetime.fromtimestamp(post.created_utc) >= datetime.strptime(authorHash[author][key], "%Y-%m-%d %H:%M:%S"):
					log.info("Messaging /u/%s that /u/%s has posted a new thread in /r/%s",key,author,subreddit)
					r.send_message(
						recipient=key,
						subject=strings.messageSubject(key),
						message=strings.alertMessage(str(post.author),subreddit,"LINK")
					)

	database.checkSubreddit(subreddit, startTimestamp)


def addUpdateSubscription(Subscriber, SubscribedTo, Subreddit, date = datetime.now(), single = True, replies = {}):
	data = {'subscriber': Subscriber.lower(), 'subscribedTo': SubscribedTo.lower(), 'subreddit': Subreddit.lower(), 'single': single}
	result = database.addSubsciption(data['subscriber'], data['subscribedTo'], data['subreddit'], date, single)
	if result:
		log.info("/u/"+data['subscriber']+" "+("updated" if single else "subscribed")+" to /u/"+data['subscribedTo']+" in /r/"+data['subreddit'])
		replies["added"].append(data)
	else:
		currentType = database.getSubscriptionType(data['subscriber'], data['subscribedTo'], data['subreddit'])
		if currentType is not single:
			database.setSubscriptionType(data['subscriber'], data['subscribedTo'], data['subreddit'], single)
			log.info("/u/"+data['subscriber']+" "+("changed from subscription to update" if single else "changed from update to subscription")+" for /u/"+data['subscribedTo']+" in /r/"+data['subreddit'])
			replies["updated"].append(data)
		else:
			log.info("/u/"+data['subscriber']+" is already "+("updated" if single else "subscribed")+" to /u/"+data['subscribedTo']+" in /r/"+data['subreddit'])
			replies["exist"].append(data)


def removeSubscription(Subscriber, SubscribedTo, Subreddit, replies = {}):
	data = {'subscriber': Subscriber.lower(), 'subscribedTo': SubscribedTo.lower(), 'subreddit': Subreddit.lower()}
	data['single'] = database.getSubscriptionType(data['subscriber'], data['subscribedTo'], data['subreddit'])
	if database.removeSubscription(data['subscriber'], data['subscribedTo'], data['subreddit']):
		log.info("/u/"+data['subscriber']+"'s removed /u/"+data['subscribedTo']+" in /r/"+data['subreddit'])
		replies["removed"].append(data)
	else:
		log.info("/u/"+data['subscriber']+"'s doesn't have a /u/"+data['subscribedTo']+" in /r/"+data['subreddit'])
		replies["notremoved"].append(data)


### Main ###
log.debug("Connecting to reddit")
r = praw.Reddit(user_agent=globals.USER_AGENT, log_request=0)
o = OAuth2Util.OAuth2Util(r)
o.refresh(force=True)

database.init()

for message in r.get_unread(unset_has_mail=True, update_user=True, limit=100):
	# checks to see as some comments might be replys and non PMs
	if isinstance(message, praw.objects.Message):
		replies = {'added': [], 'updated': [], 'exist': [], 'removed': [], 'notremoved': [], 'list': False}
		log.info("Parsing message from /u/"+str(message.author))
		for line in message.body.lower().splitlines():
			log.debug("line: "+line)
			if line.startswith("updateme") or line.startswith("subscribeme"):
				users = re.findall('(?:/u/)(\w*)', line)
				subs = re.findall('(?:/r/)(\w*)', line)
				links = re.findall('(?:reddit.com/r/\w*/comments/)(\w*)', line)

				if len(links) != 0:
					log.debug("Parsing link")
					submission = r.get_submission(submission_id=links[0])
					users.append(str(submission.author))
					subs.append(str(submission.subreddit))

				if len(users) != 0 and len(subs) != 0 and not (len(users) > 1 and len(subs) > 1):
					subscriptionType = True if line.startswith("updateme") else False
					if len(users) > 1:
						for user in users:
							addUpdateSubscription(str(message.author), user, subs[0], datetime.fromtimestamp(message.created_utc), subscriptionType, replies)
					elif len(subs) > 1:
						for sub in subs:
							addUpdateSubscription(str(message.author), users[0], sub, datetime.fromtimestamp(message.created_utc), subscriptionType, replies)
					else:
						addUpdateSubscription(str(message.author), users[0], subs[0], datetime.fromtimestamp(message.created_utc), subscriptionType, replies)

			elif line.startswith("removeall"):
				log.info("Removing all subscriptions for /u/"+str(message.author).lower())
				replies['removed'].extend(database.getMySubscriptions(str(message.author).lower()))
				database.removeAllSubscriptions(str(message.author).lower())

			elif line.startswith("remove"):
				users = re.findall('(?:/u/)(\w*)', line)
				subs = re.findall('(?:/r/)(\w*)', line)

				if len(users) != 0 and len(subs) != 0 and not (len(users) > 1 and len(subs) > 1):
					if len(users) > 1:
						for user in users:
							removeSubscription(str(message.author), user, subs[0], replies)
					elif len(subs) > 1:
						for sub in subs:
							removeSubscription(str(message.author), users[0], sub, replies)
					else:
						removeSubscription(str(message.author), users[0], subs[0], replies)

			elif (line.startswith("mysubscriptions") or line.startswith("myupdates")) and not replies['list']:
				replies['list'] = True

		#message.mark_as_read()

		strList = []
		sectionCount = 0

		if replies['added']:
			sectionCount += 1
			strList.extend(strings.confirmationSection(replies['added']))
			strList.append("\n\n*****\n\n")
		if replies['updated']:
			sectionCount += 1
			strList.extend(strings.updatedSubscriptionSection(replies['updated']))
			strList.append("\n\n*****\n\n")
		if replies['exist']:
			sectionCount += 1
			strList.extend(strings.alreadySubscribedSection(replies['exist']))
			strList.append("\n\n*****\n\n")
		if replies['removed']:
			sectionCount += 1
			strList.extend(strings.removeUpdatesConfirmationMessage(replies['removed']))
			strList.append("\n\n*****\n\n")
		if replies['list']:
			sectionCount += 1
			strList.extend(strings.yourUpdatesSection(database.getMySubscriptions(str(message.author).lower())))
			strList.append("\n\n*****\n\n")

		if sectionCount == 0:
			log.info("Nothing found in message")
			strList.append(strings.couldNotUnderstandMessage)
			strList.append("\n\n*****\n\n")

		strList.append(strings.footer)

		log.debug("Sending message:")
		log.debug(''.join(strList))
		message.reply(''.join(strList))






prevSubreddit = None
subs = {}
oldestTimestamp = None
for row in database.getSubscriptions():
	if row[SUBREDDIT_NUM] != prevSubreddit:
		searchSubreddit(prevSubreddit, subs, oldestTimestamp)
		subs = {}
		oldestTimestamp = row[LASTCHECKED_NUM]

	if row[SUBSCRIBEDTO_NUM] not in subs:
		subs[row[SUBSCRIBEDTO_NUM]] = {}

	subs[row[SUBSCRIBEDTO_NUM]][row[SUBSCRIBER_NUM]] = row[LASTCHECKED_NUM]

	prevSubreddit = row[SUBREDDIT_NUM]

searchSubreddit(prevSubreddit, subs, oldestTimestamp)

database.close()
