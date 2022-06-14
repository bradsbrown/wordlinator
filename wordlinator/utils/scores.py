import collections
import typing

import wordlinator.db.pg
import wordlinator.twitter

############
# Mappings #
############

SCORE_NAME_MAP = {
    1: "Hole-in-1",
    2: "Eagle",
    3: "Birdie",
    4: "Par",
    5: "Bogey",
    6: "Double Bogey",
    7: "Fail",
}


###############
# ScoreMatrix #
###############

T = typing.TypeVar("T", bound="ScoreContainer")
Score = wordlinator.db.pg.Score
User = wordlinator.db.pg.User
Hole = wordlinator.db.pg.Hole
WordleTweet = wordlinator.twitter.WordleTweet


class ScoreContainer:
    def __init__(self, scores: typing.List[Score]):
        self._scores = scores

    @staticmethod
    def _get_attribute(score: Score, attribute_path: typing.List[str]):
        attribute = score
        for path_part in attribute_path:
            attribute = getattr(attribute, path_part)
        return attribute

    def dict_by(
        self, attribute_path: str, container_class: typing.Type[T]
    ) -> typing.Dict[typing.Any, T]:
        data_dict = collections.defaultdict(list)
        path_parts = attribute_path.split(".")

        for score in self._scores:
            data_dict[self._get_attribute(score, path_parts)].append(score)

        return {k: container_class(v) for k, v in data_dict.items()}


class ScoreRow(ScoreContainer):
    @property
    def total(self) -> int:
        return sum(s.score for s in self._scores)

    @property
    def count(self) -> int:
        return len(self._scores)

    @property
    def average(self) -> float:
        return round(self.total / len(self._scores), 2)


class UserRow(ScoreRow):
    def __init__(self, scores, username=None):
        super().__init__(scores)
        self.username = username or scores[0].user_id.username

    @property
    def golf_score(self) -> int:
        return self.total - (self.count * 4)

    def sorted_scores(self):
        yield from sorted(self._scores, key=lambda s: s.hole_id.hole)

    def raw_values(self):
        yield from (s.score for s in self.sorted_scores())

    def _present_format(self, score):
        if score.tweet_id:
            return (
                f"[{score.score}]"
                f"(https://twitter.com/{self.username}/status/{score.tweet_id})"
            )
        return score.score

    def presentation_values(self, hole_no=None):
        res = {s.hole_id.hole: self._present_format(s) for s in self.sorted_scores()}
        if hole_no:
            for i in range(1, hole_no + 1):
                if i not in res:
                    res[i] = ""
        return res

    def user_row(self, hole_no=None):
        return {
            "Name": self.username,
            "Score": self.golf_score,
            **self.presentation_values(hole_no=hole_no),
        }

    def get_changes(
        self,
        sheets_scores: typing.List[int],
        twitter_score: typing.Optional[WordleTweet],
        db_user: User,
        db_holes: typing.List[Hole],
    ) -> typing.Dict[str, typing.List[Score]]:
        current_scores = list(self.sorted_scores())

        results: typing.Dict[str, typing.List[typing.Any]] = {
            "update": [],
            "create": [],
        }

        for day, score in enumerate(sheets_scores, start=1):
            try:
                score = int(score)
            except ValueError:
                continue

            hole = [h for h in db_holes if h.hole == day][0]
            score_match = [s for s in current_scores if s.hole_id.hole == day]

            tweet_id = None
            if twitter_score and twitter_score.wordle_day.golf_hole.hole_no == day:
                tweet_id = twitter_score.tweet_id

            if not score_match:
                results["create"].append(
                    {
                        "score": score,
                        "user_id": db_user.user_id,
                        "game_id": hole.game_id.game_id,
                        "hole_id": hole.hole_id,
                        "tweet_id": tweet_id,
                    }
                )
            else:
                saved_score = score_match[0]
                if saved_score.score != score or saved_score.tweet_id != tweet_id:
                    saved_score.score = score
                    saved_score.tweet_id = tweet_id
                    results["update"].append(saved_score)

        return results


class ScoreMatrix(ScoreContainer):
    def by_user(self):
        return self.dict_by("user_id.username", UserRow)

    def for_user(self, username):
        user_scores = [s for s in self._scores if s.user_id.username == username]
        return UserRow(scores=user_scores, username=username)

    def by_hole(self):
        return self.dict_by("hole_id.hole", ScoreRow)

    def for_hole(self, hole_no):
        hole_scores = [s for s in self._scores if s.hole_id.hole == hole_no]
        return ScoreRow(hole_scores)

    def _level_counts(self, level_scores: "ScoreMatrix"):
        hole_dict = level_scores.by_hole()
        return {k: v.count for k, v in sorted(hole_dict.items())}

    def score_breakdown(self):
        by_score_dict = self.dict_by("score", ScoreMatrix)
        return {
            SCORE_NAME_MAP[k]: self._level_counts(v)
            for k, v in sorted(by_score_dict.items())
        }

    def user_rows(self, wordle_day):
        hole_no = wordle_day.golf_hole.hole_no
        return [u.user_row(hole_no=hole_no) for u in self.by_user().values()]
