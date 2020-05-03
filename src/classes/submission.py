from sqlalchemy import Column, Integer, String,  DateTime, ForeignKey
from database import Base
from sqlalchemy.orm import relationship

import utils
import static


class Submission(Base):
	__tablename__ = 'submissions'

	id = Column(Integer, primary_key=True)
	submission_id = Column(String(12), nullable=False, unique=True)
	time_scanned = Column(DateTime(), nullable=False)
	time_created = Column(DateTime(), nullable=False)
	author_name = Column(String(80), nullable=False)
	url = Column(String(200), nullable=False)
	messages_sent = Column(Integer, nullable=False)
	tag = Column(String(200, collation="NOCASE"))
	subreddit_id = Column(Integer, ForeignKey('subreddits.id'), nullable=False)

	comment = relationship("DbComment", uselist=False, back_populates="submission", lazy="joined")
	subreddit = relationship("Subreddit", lazy="joined")

	def __init__(
		self,
		submission_id,
		time_created,
		author_name,
		subreddit,
		permalink,
		tag=None,
		messages_sent=0
	):
		self.submission_id = submission_id
		self.time_created = time_created
		self.time_scanned = utils.datetime_now()
		self.author_name = author_name
		self.subreddit = subreddit
		self.url = "https://www.reddit.com" + permalink
		self.tag = tag
		self.messages_sent = messages_sent

	def __str__(self):
		return \
			f"u/{self.author_name} to r/{self.subreddit.name} : " \
			f"u/{self.submission_id}{(' <'+self.tag+'>' if self.tag is not None else '')}"

	def render_prompt(self):
		bldr = utils.str_bldr()
		if self.tag is not None:
			bldr.append("[Click here](")
			bldr.append(utils.build_message_link(
				static.ACCOUNT_NAME,
				"Subscribe",
				f"SubscribeMe u/{self.author_name} r/{self.subreddit.name} <{self.tag}>"
			))
			bldr.append(") to subscribe to u/")
			bldr.append(self.author_name)
			bldr.append(" and receive a message every time they post a new post tagged <")
			bldr.append(self.tag)
			bldr.append(">.  \nOr")

		bldr.append("[Click here](")
		bldr.append(utils.build_message_link(
			static.ACCOUNT_NAME,
			"Subscribe",
			f"SubscribeMe u/{self.author_name} r/{self.subreddit.name}"
		))
		bldr.append(") to subscribe to u/")
		bldr.append(self.author_name)
		bldr.append(" and receive a message every time they post")

		if self.tag is not None:
			bldr.append(" any tag")

		bldr.append(".")
		return bldr
