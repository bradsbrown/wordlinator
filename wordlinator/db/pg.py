import os
import typing

import peewee

import wordlinator.utils

db = peewee.PostgresqlDatabase(
    os.getenv("DB_NAME", "wordlegolf"),
    user=os.getenv("DB_USER", "wordlegolf"),
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),
    password=os.environ["DB_PASS"],
)


class BaseModel(peewee.Model):
    class Meta:
        database = db


class User(BaseModel):
    user_id = peewee.AutoField()
    username = peewee.CharField(unique=True)
    twitter_id = peewee.CharField(unique=True)
    check_twitter = peewee.BooleanField(default=True)

    class Meta:
        table_name = "user_tbl"


class Game(BaseModel):
    game_id = peewee.AutoField()
    game = peewee.IntegerField(null=False)
    start_date = peewee.DateField(null=False)


class Player(BaseModel):
    user_id = peewee.ForeignKeyField(User, "user_id", null=False)
    game_id = peewee.ForeignKeyField(Game, "game_id", null=False)


class Hole(BaseModel):
    hole_id = peewee.AutoField()
    hole = peewee.IntegerField(null=False)
    game_id = peewee.ForeignKeyField(Game, "game_id", null=False)


class Score(BaseModel):
    score = peewee.IntegerField(null=False)
    user_id = peewee.ForeignKeyField(User, "user_id", null=False)
    game_id = peewee.ForeignKeyField(Game, "game_id", null=False)
    hole_id = peewee.ForeignKeyField(Hole, "hole_id", null=False)

    class Meta:
        primary_key = peewee.CompositeKey("user_id", "game_id", "hole_id")


class WordleDb:
    def get_user(self, username):
        try:
            return User.get(User.username == username)
        except peewee.DoesNotExist:
            return None

    def get_users(self):
        return list(User.select())

    def get_user_id(self, username):
        user = self.get_user(username)
        return user.twitter_id if user else None

    def add_user(self, username, user_id):
        return User.create(username=username, twitter_id=user_id)

    def get_or_create_round(self, round_no, start_date=None):
        try:
            return Game.get(Game.game == round_no)
        except peewee.DoesNotExist:
            start_date = (
                start_date or wordlinator.utils.WORDLE_GOLF_ROUND_DATES[round_no - 1]
            )
            return Game.create(game=round_no, start_date=start_date)

    def get_or_create_hole(self, round_no, hole_no):
        round = self.get_or_create_round(round_no)

        try:
            return Hole.get(Hole.hole == hole_no, Hole.game_id == round.game_id)
        except peewee.DoesNotExist:
            return Hole.create(hole=hole_no, game_id=round.game_id)

    def get_holes(self, round_no):
        round = self.get_or_create_round(round_no)
        return list(Hole.select().filter(game_id=round.game_id))

    def create_round_holes(self, round_no):
        for hole_no in range(1, 19):
            self.get_or_create_hole(round_no, hole_no)

    def add_score(self, username, game, hole, score):
        if not score:
            return

        user = self.get_user(username)
        if not user:
            raise ValueError(f'No Such User "{username}"')
        hole = self.get_or_create_hole(game, hole)

        try:
            score_obj = Score.get(
                Score.user_id == user.user_id,
                Score.game_id == hole.game_id,
                Score.hole_id == hole.hole_id,
            )
            score_obj.score = score
            score_obj.save()
            return score_obj
        except peewee.DoesNotExist:
            return Score.create(
                score=score,
                user_id=user.user_id,
                game_id=hole.game_id,
                hole_id=hole.hole_id,
            )

    def get_scores(self, round_no):
        round = self.get_or_create_round(round_no)
        res = (
            Score.select(Score, Player.game_id)
            .join(Player, on=(Score.user_id == Player.user_id))
            .filter(Player.game_id == round.game_id)
            .filter(Score.game_id == round.game_id)
        )
        return list(res)

    def bulk_insert_scores(self, scores: typing.List[typing.Dict]):
        with db.atomic():
            for batch in peewee.chunked(scores, 50):
                Score.insert_many(batch).execute()

    def bulk_update_scores(self, scores: typing.List[Score]):
        with db.atomic():
            for score in scores:
                score.save()

    def get_users_without_score(self, round_no, hole_no, tweetable=True):
        hole = self.get_or_create_hole(round_no, hole_no)
        # Find users who *have* played in this round,
        # but have no score on the current hole
        query_str = """SELECT u.username, player.game_id
        FROM user_tbl u
        JOIN player ON player.user_id = u.user_id
        WHERE (
            player.game_id = {}
        ) AND NOT EXISTS (
            SELECT FROM score WHERE score.user_id = u.user_id AND score.hole_id = {}
        )
        """.format(
            hole.game_id, hole.hole_id
        )

        if tweetable:
            # Restrict to users who post scores on twitter
            query_str += " AND u.check_twitter = true"

        res = db.execute_sql(query_str)
        return [r[0] for r in res]
