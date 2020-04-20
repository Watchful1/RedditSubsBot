from enum import Enum


class ReturnType(Enum):
	SUCCESS = 1
	INVALID_USER = 2
	USER_DOESNT_EXIST = 3
	FORBIDDEN = 4
	THREAD_LOCKED = 5
	DELETED_COMMENT = 6
	QUARANTINED = 7
	RATELIMIT = 8
	THREAD_REPLIED = 9
	NOTHING_RETURNED = 10
	SUBREDDIT_NOT_ENABLED = 11
	SUBMISSION_NOT_PROCESSED = 12
