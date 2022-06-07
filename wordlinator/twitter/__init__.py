import asyncio
import dataclasses
import datetime
import enum
import os
import re
import urllib.parse
import webbrowser

import authlib.integrations.httpx_client
import dateutil.parser
import httpx
import rich

import wordlinator.db.pg
import wordlinator.utils

BASE_URL = "https://api.twitter.com/2"
WORDLE_RE = re.compile(
    r"Wordle(\w+)? (?P<number>\d+) (?P<score>[X\d])/6", re.IGNORECASE
)
TOKEN = os.getenv("TWITTER_TOKEN")


def _get_oauth_creds():
    creds = {
        "client_id": os.getenv("TWITTER_API_KEY"),
        "client_secret": os.getenv("TWITTER_API_KEY_SECRET"),
        "token": os.getenv("TWITTER_USER_TOKEN"),
        "token_secret": os.getenv("TWITTER_USER_TOKEN_SECRET"),
    }
    if not all(creds.values()):
        return None
    return creds


@dataclasses.dataclass
class TwitterUser:
    name: str
    handle: str


class ScoreName(enum.Enum):
    Ace = -4
    Albatross = -3
    Eagle = -2
    Birdie = -1
    Par = 0
    Bogey = 1
    Double_Bogey = 2
    Bust = 3


@dataclasses.dataclass
class WordleTweet:
    PAR = 4

    created_at: datetime.datetime
    text: str
    wordle_day: wordlinator.utils.WordleDay
    raw_score: int
    user: TwitterUser

    @property
    def score(self):
        return self.raw_score - self.PAR

    @property
    def score_name(self):
        return ScoreName(self.score).name

    @classmethod
    def from_tweet(cls, tweet, users):
        wordle = WORDLE_RE.search(tweet["text"])
        if not wordle:
            return None

        wordle_no = int(wordle.groupdict()["number"])
        score = wordle.groupdict()["score"]
        score = int(score) if score.isdigit() else 7

        user = [u for u in users if u["id"] == tweet["author_id"]][0]

        twitter_user = TwitterUser(name=user["name"], handle=user["username"])
        created = dateutil.parser.parse(tweet["created_at"])
        return cls(
            created_at=created,
            text=tweet["text"],
            wordle_day=wordlinator.utils.WordleDay.from_wordle_no(wordle_no),
            raw_score=score,
            user=twitter_user,
        )


class TwitterClient(httpx.AsyncClient):
    SEARCH_PATH = "tweets/search/recent"
    USER_PATH = "users/by/username/{username}"
    TWEETS_PATH = "users/{user_id}/tweets"
    POST_TWEET_PATH = "tweets"

    TWEET_INTENT_URL = "https://twitter.com/intent/tweet"

    MAX_TWEET_LENGTH = 260

    def __init__(
        self,
        wordle_day: wordlinator.utils.WordleDay = wordlinator.utils.WORDLE_TODAY,
        **kwargs,
    ):
        oauth_creds = _get_oauth_creds()
        if oauth_creds:
            auth = authlib.integrations.httpx_client.OAuth1Auth(**oauth_creds)
            kwargs["auth"] = auth
        super().__init__(base_url=BASE_URL, **kwargs)
        self.db = wordlinator.db.pg.WordleDb()
        self.wordle_day = wordle_day
        if not oauth_creds:
            self.headers["Authorization"] = f"Bearer {TOKEN}"

    async def search_tweets(self, search_str):
        return await self.get(
            self.SEARCH_PATH,
            params={
                "query": search_str,
                "tweet.fields": "created_at",
                "expansions": "author_id",
                "max_results": "100",
            },
        )

    async def get_user_by(self, username: str):
        return await self.get(self.USER_PATH.format(username=username))

    async def get_user_id(self, username: str):
        db_user = self.db.get_user(username)
        if db_user:
            return db_user.twitter_id if db_user.check_twitter else False
        else:
            twitter_user = await self.get_user_by(username)
            user_id = None
            if twitter_user.is_success:
                user_id = twitter_user.json().get("data", {}).get("id", None)
            if user_id:
                self.db.add_user(username, user_id)
            return user_id

    def _start_timestamp(self):
        day = self.wordle_day.date - datetime.timedelta(days=1)
        dt = datetime.datetime(
            day.year, day.month, day.day, 16, 00, 00, tzinfo=datetime.timezone.utc
        )
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    async def get_user_recent_tweets(self, user_id: str):
        return await self.get(
            self.TWEETS_PATH.format(user_id=user_id),
            params={
                "max_results": 100,
                "expansions": "author_id",
                "tweet.fields": "created_at",
                "start_time": self._start_timestamp(),
            },
        )

    async def get_user_tweets_by(self, username: str):
        user_id = await self.get_user_id(username)
        if not user_id:
            return user_id
        return await self.get_user_recent_tweets(user_id)

    async def get_user_wordles(self, username):
        user_tweets = await self.get_user_tweets_by(username)
        if user_tweets and not user_tweets.is_success:
            rich.print(
                f"[red]Get tweets failed for {username} -- "
                f"{user_tweets.status_code}: {user_tweets.text}"
            )
        if not user_tweets:
            if user_tweets is None:
                rich.print(f"[yellow]No User ID found for {username}")
            if user_tweets is False:
                rich.print(f"[blue]Skipping check for {username}")
            return []
        return self._build_wordle_tweets(user_tweets)

    def _build_wordle_tweets(self, response: httpx.Response):
        res_json = response.json()
        if "data" not in res_json:
            return []
        tweets = res_json["data"]
        users = res_json["includes"]["users"]
        return list(
            filter(None, map(lambda t: WordleTweet.from_tweet(t, users), tweets))
        )

    async def get_wordlegolf_tweets(self):
        return self._build_wordle_tweets(await self.search_tweets("#WordleGolf"))

    @classmethod
    def open_tweet(cls, msg):
        param = urllib.parse.urlencode({"text": msg})
        webbrowser.open(f"{cls.TWEET_INTENT_URL}?{param}")

    @classmethod
    def full_notify_link(cls, names):
        header = "Still missing a few #WordleGolf Players today!"
        msg = header
        while names:
            msg += f" @{names.pop()}"
        param = urllib.parse.urlencode({"text": msg})
        return f"{cls.TWEET_INTENT_URL}?{param}"

    @classmethod
    async def notify_missing(cls, names):
        header = "Still missing a few #WordleGolf Players today!"
        msg = header
        while names:
            while len(msg) < cls.MAX_TWEET_LENGTH and names:
                msg += f" @{names.pop()}"
            cls.open_tweet(msg)


async def main():
    client = TwitterClient()
    rich.print(await client.get_user_wordles("zoocat"))
    rich.print(await client.get_wordlegolf_tweets())


if __name__ == "__main__":
    asyncio.run(main())
