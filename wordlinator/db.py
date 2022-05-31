import sqlite3


class WordleDb:
    def __init__(self):
        self.con = sqlite3.connect("wordle.db")
        cur = self.con.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS user
            (id INTEGER PRIMARY KEY,
             username varchar(50) NOT NULL,
             user_id varchar(20) NOT NULL)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS game (
                id INTEGER PRIMARY KEY,
                game INTEGER NOT NULL)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS hole
            (id INTEGER PRIMARY KEY,
             hole INTEGER NOT NULL,
             game_id INTEGER NOT NULL,
             FOREIGN KEY (game_id)
               REFERENCES game (id)
             )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS score
           (id INTEGER PRIMARY KEY,
            score INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            hole_id INTEGER NOT NULL,
            FOREIGN KEY (game_id)
              REFERENCES game (id),
            FOREIGN KEY (user_id)
              REFERENCES user (id),
            FOREIGN KEY (hole_id)
              REFERENCES hole (id),
            UNIQUE(user_id, game_id, hole_id)
            )"""
        )
        self.con.commit()

    def get_user(self, username):
        cur = self.con.cursor()
        res = list(cur.execute(f"SELECT * FROM user WHERE username = '{username}'"))
        return res[0] if res else None

    def get_user_id(self, username):
        user = self.get_user(username)
        if not user:
            return None
        return user[2]

    def add_user(self, username, user_id):
        cur = self.con.cursor()
        cur.execute(
            f"INSERT INTO user (username, user_id) VALUES ('{username}', '{user_id}')"
        )
        self.con.commit()

    def get_or_create_round(self, round_no):
        cur = self.con.cursor()
        res = list(cur.execute(f"SELECT * FROM game WHERE game = {round_no}"))
        if not res:
            list(cur.execute(f"INSERT INTO game (game) VALUES ({round_no})"))
            self.con.commit()
            res = list(cur.execute(f"SELECT * FROM game WHERE game = {round_no}"))
        return res[0]

    def get_or_create_hole(self, round_no, hole_no):
        round_id = self.get_or_create_round(round_no)[0]
        cur = self.con.cursor()
        res = list(
            cur.execute(
                f"SELECT * FROM hole WHERE hole = {hole_no} AND game_id = {round_id}"
            )
        )
        if not res:
            cur.execute(
                f"INSERT INTO hole (hole, game_id) VALUES ({hole_no}, {round_id})"
            )
            res = list(
                cur.execute(
                    "SELECT * FROM hole "
                    f"WHERE hole = {hole_no} AND game_id = {round_id}"
                )
            )
        self.con.commit()
        return res[0]

    def create_round_holes(self, round_no):
        for hole_no in range(1, 19):
            self.get_or_create_hole(round_no, hole_no)

    def add_score(self, username, game, hole, score):
        if not score:
            return
        user = self.get_user(username)
        if not user:
            raise ValueError("No such user!")
        user_id = user[0]

        hole = self.get_or_create_hole(game, hole)
        _, hole_id, game_id = hole

        cur = self.con.cursor()
        res = list(
            cur.execute(
                f"""SELECT score FROM score
            WHERE user_id = {user_id} AND game_id = {game_id} AND hole_id = {hole_id}"""
            )
        )
        if res:
            cmd = f"""UPDATE score
                SET score = {score}
                WHERE user_id = {user_id}
                  AND game_id = {game_id}
                  AND hole_id = {hole_id}"""
        else:
            cmd = f"""INSERT INTO score (score, user_id, game_id, hole_id)
                VALUES ({score}, {user_id}, {game_id}, {hole_id})"""
        cur.execute(cmd)
        self.con.commit()
