import asyncio
import dataclasses
import datetime
import enum
import os
import re

import dateutil.parser
import httpx
import rich

BASE_URL = "https://api.twitter.com/2"
WORDLE_RE = re.compile(r"Wordle (?P<number>\d+) (?P<score>[X\d])/6")
TOKEN = os.getenv("TWITTER_TOKEN")


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
    wordle_no: int
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
            wordle_no=wordle_no,
            raw_score=score,
            user=twitter_user,
        )


class TwitterClient(httpx.AsyncClient):
    SEARCH_PATH = "tweets/search/recent"

    def __init__(self, **kwargs):
        super().__init__(base_url=BASE_URL, **kwargs)
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

    def _build_wordle_tweets(self, response: httpx.Response):
        res_json = response.json()
        if "data" not in res_json:
            return []
        tweets = res_json["data"]
        users = res_json["includes"]["users"]
        return list(
            filter(None, map(lambda t: WordleTweet.from_tweet(t, users), tweets))
        )

    async def get_user_wordles(self, username):
        return self._build_wordle_tweets(
            await self.search_tweets(f"from:{username} wordle")
        )

    async def get_wordlegolf_tweets(self):
        return self._build_wordle_tweets(await self.search_tweets("#WordleGolf"))


async def main():
    client = TwitterClient()
    rich.print(await client.get_user_wordles("zoocat"))
    rich.print(await client.get_wordlegolf_tweets())


if __name__ == "__main__":
    asyncio.run(main())
