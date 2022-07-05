import datetime
import os
import typing

import peewee

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

    def __repr__(self):
        return f"<User {self.username}, Check Twitter: {self.check_twitter}>"

    class Meta:
        table_name = "user_tbl"


class Game(BaseModel):
    game_id = peewee.AutoField()
    game = peewee.IntegerField(null=False)
    start_date = peewee.DateField(null=False)

    def __repr__(self):
        return f"<Game: Round {self.game}, Start {self.start_date}>"

    @property
    def end_date(self):
        return self.start_date + datetime.timedelta(days=17)


class Player(BaseModel):
    user_id = peewee.ForeignKeyField(User, "user_id", null=False)
    game_id = peewee.ForeignKeyField(Game, "game_id", null=False)

    class Meta:
        primary_key = peewee.CompositeKey("user_id", "game_id")


class Hole(BaseModel):
    hole_id = peewee.AutoField()
    hole = peewee.IntegerField(null=False)
    game_id = peewee.ForeignKeyField(Game, "game_id", null=False)

    def __repr__(self):
        return f"<Hole #{self.hole}>"


class Score(BaseModel):
    score = peewee.IntegerField(null=False)
    user_id = peewee.ForeignKeyField(User, "user_id", null=False)
    game_id = peewee.ForeignKeyField(Game, "game_id", null=False)
    hole_id = peewee.ForeignKeyField(Hole, "hole_id", null=False)
    tweet_id = peewee.CharField(max_length=255, null=True)

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

    def get_users_by_round(self, round_no=None, round_id=None):
        with db.atomic():
            query = (
                User.select(User, Player.user_id, Game.game)
                .join(Player, on=(Player.user_id == User.user_id))
                .join(Game, on=(Game.game_id == Player.game_id))
            )
            if round_no:
                query = query.filter(Game.game == round_no)
            elif round_id:
                query = query.filter(Game.game_id == round_id)
            return list(query)

    def get_user_id(self, username):
        with db.atomic():
            user = self.get_user(username)
            return user.twitter_id if user else None

    def add_user(self, username, user_id, check_twitter=True):
        with db.atomic():
            return User.create(
                username=username, twitter_id=user_id, check_twitter=check_twitter
            )

    def get_rounds(self):
        with db.atomic():
            return list(sorted(Game.select(), key=lambda d: d.start_date))

    def get_or_create_round(self, round_no, start_date=None):
        with db.atomic():
            try:
                return Game.get(Game.game == round_no)
            except peewee.DoesNotExist:
                if not start_date:
                    raise ValueError(
                        f"Round {round_no} does not exist, "
                        "and no start_date provide to create it"
                    )
                return Game.create(game=round_no, start_date=start_date)

    def get_or_create_hole(self, round_no, hole_no):
        with db.atomic():
            round = self.get_or_create_round(round_no)

            try:
                return Hole.get(Hole.hole == hole_no, Hole.game_id == round.game_id)
            except peewee.DoesNotExist:
                return Hole.create(hole=hole_no, game_id=round.game_id)

    def get_holes(self, round_no, ensure_all=False):
        with db.atomic():
            round = self.get_or_create_round(round_no)
            if ensure_all:
                self.create_round_holes(round_no)
            return list(Hole.select().filter(game_id=round.game_id))

    def create_round_holes(self, round_no):
        with db.atomic():
            for hole_no in range(1, 19):
                self.get_or_create_hole(round_no, hole_no)

    def get_or_create_player_round(self, user_id, game_id):
        with db.atomic():
            try:
                return Player.get(Player.user_id == user_id, Player.game_id == game_id)
            except peewee.DoesNotExist:
                return Player.create(user_id=user_id, game_id=game_id)

    def add_user_to_round(self, username, round_no):
        with db.atomic():
            user = self.get_user(username)
            if not user:
                raise ValueError(f"No user found with username {username}")
            round = self.get_or_create_round(round_no)
            return self.get_or_create_player_round(user.user_id, round.game_id)

    def remove_user_from_round(self, username, round_no):
        with db.atomic():
            user = self.get_user(username)
            if not user:
                raise ValueError(f"No user found with username {username}")
            round = self.get_or_create_round(round_no)
            try:
                player = Player.get(user_id=user.user_id, game_id=round.game_id)
                player.delete_instance()
            except peewee.DoesNotExist:
                return

    def copy_players_from_round(self, from_round_no, to_round_no):
        with db.atomic():
            to_round = self.get_or_create_round(to_round_no)

            for user in self.get_users_by_round(from_round_no):
                self.get_or_create_player_round(user.user_id, to_round.game_id)

    def add_score(self, username, game, hole, score):
        with db.atomic():
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

    def get_scores(self, round_no=None, round_id=None):
        with db.atomic():
            if round_no:
                round = self.get_or_create_round(round_no)
            elif round_id:
                round = Game.get_by_id(round_id)
            else:
                raise ValueError("Must provide Round Number or Round ID")
            res = (
                Score.select(
                    Score,
                    Hole.hole,
                    Hole.hole_id,
                    Game.game_id,
                    User.username,
                    User.user_id,
                    Player.game_id,
                )
                .join(Player, on=(Score.user_id == Player.user_id))
                .switch(Score)
                .join(Hole, on=(Score.hole_id == Hole.hole_id))
                .join(Game, on=(Hole.game_id == Game.game_id))
                .switch(Score)
                .join(User, on=(Score.user_id == User.user_id))
                .filter(Player.game_id == round.game_id)
                .filter(Score.game_id == round.game_id)
            )
            return list(res) if res else []

    def bulk_insert_scores(self, scores: typing.List[typing.Dict]):
        with db.atomic() as txn:
            for batch in peewee.chunked(scores, 50):
                Score.insert_many(batch).execute()

    def bulk_update_scores(self, scores: typing.List[Score]):
        query_str = """UPDATE score
        SET score = {score}, tweet_id = {tweet_id}
        WHERE user_id = {user_id} AND game_id = {game_id} AND hole_id = {hole_id}"""
        for score in scores:
            query = query_str.format(
                score=score.score,
                tweet_id=score.tweet_id or "NULL",
                user_id=score.user_id.user_id,
                game_id=score.game_id.game_id,
                hole_id=score.hole_id.hole_id,
            )
            db.execute_sql(query)

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
