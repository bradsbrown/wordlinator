import argparse
import asyncio

import rich
import rich.progress
import rich.table

import wordlinator.db.pg
import wordlinator.sheets
import wordlinator.twitter
import wordlinator.utils
import wordlinator.utils.scores


async def get_scores(
    wordle_day: wordlinator.utils.WordleDay = wordlinator.utils.WORDLE_TODAY,
):
    users = wordlinator.sheets.SheetsClient(wordle_day=wordle_day).get_missing_names()

    twitter_client = wordlinator.twitter.TwitterClient(wordle_day=wordle_day)

    scores = {}

    for user in rich.progress.track(users, description="Checking for user scores.."):
        user_scores = await twitter_client.get_user_wordles(user)
        day_score = [s for s in user_scores if s.wordle_day == wordle_day]
        scores[user] = day_score[0] if day_score else None
        await asyncio.sleep(1)

    return scores


def print_missing_names(wordle_day, names):
    table = rich.table.Table(
        "Missing Players", title=f"Missing Wordle Scores Day {wordle_day.wordle_no}"
    )
    for name in names:
        table.add_row(name)
    rich.print(table)


def print_score_table(wordle_day, scores):
    score_table = rich.table.Table(
        rich.table.Column(header="Username", style="green"),
        rich.table.Column("Raw Score"),
        rich.table.Column("Golf Score"),
        rich.table.Column("Score Name"),
        title=f"Wordle Scores Day {wordle_day.wordle_no}",
    )
    scoreless_names = []
    for username, score in scores.items():
        args = [username]
        if score:
            raw_score = score.raw_score
            if raw_score < 4:
                color = "green"
            elif raw_score == 4:
                color = "orange3"
            elif raw_score > 6:
                color = "red"
            else:
                color = "yellow"

            score_args = [raw_score, score.score, score.score_name]
            args += [f"[{color}]{arg}" for arg in score_args]
            score_table.add_row(*args)
        else:
            scoreless_names.append(username)
    rich.print(score_table)
    print_missing_names(wordle_day, scoreless_names)


def _save_db_scores(
    wordle_day: wordlinator.utils.WordleDay, scores: dict, twitter_scores=None
):
    twitter_scores = twitter_scores or {}
    db = wordlinator.db.pg.WordleDb()
    hole_data = wordle_day.golf_hole
    if not hole_data:
        return
    game_no = hole_data.game_no

    db_users = db.get_users()
    db_holes = db.get_holes(game_no, ensure_all=True)
    db_scores = db.get_scores(game_no)

    db_scores_by_user = wordlinator.utils.scores.ScoreMatrix(db_scores).by_user(
        usernames=list(scores.keys())
    )

    to_update = []
    to_create = []

    for user, score_list in scores.items():
        db_user_scores = db_scores_by_user.get(user)
        if not db_user_scores:
            continue
        db_user_match = [u for u in db_users if u.username == user]
        if not db_user_match:
            rich.print(f"[yellow]User {user} not in database, cannot add scores.")
            continue
        db_user = db_user_match[0]
        twitter_score = twitter_scores.get(user, None)
        changes = db_user_scores.get_changes(
            score_list, twitter_score, db_user, db_holes
        )
        to_update.extend(changes["update"])
        to_create.extend(changes["create"])

    if to_update:
        db.bulk_update_scores(to_update)

    if to_create:
        db.bulk_insert_scores(to_create)
    return


async def main_update(
    wordle_day: wordlinator.utils.WordleDay = wordlinator.utils.WORDLE_TODAY,
):
    if not wordle_day.golf_hole:
        rich.print(f"[yellow]{wordle_day.date} isn't a #WordleGolf day!")
        exit()
    sheets_client = wordlinator.sheets.SheetsClient(wordle_day=wordle_day)

    today_scores = await get_scores(wordle_day=wordle_day)
    if not any((s is not None for s in today_scores.values())):
        rich.print("[blue]No new scores found!")
    else:
        rich.print("[green]Updating scores in Sheets...")
        updated_scores = sheets_client.update_scores(today_scores)

        rich.print("[green]Saving scores in db...")
        _save_db_scores(wordle_day, updated_scores, today_scores)

    print_score_table(wordle_day, today_scores)


async def main(wordle_day=wordlinator.utils.WORDLE_TODAY):
    scores = await get_scores(wordle_day)
    print_score_table(wordle_day, scores)


async def show_user(username: str):
    client = wordlinator.twitter.TwitterClient()
    scores = await client.get_user_wordles(username)
    rich.print(scores)


async def show_missing(
    wordle_day: wordlinator.utils.WordleDay = wordlinator.utils.WORDLE_TODAY,
):
    client = wordlinator.sheets.SheetsClient(wordle_day=wordle_day)
    missing_names = client.get_missing_names()
    print_missing_names(wordle_day, missing_names)


async def tweet_missing():
    sheets_client = wordlinator.sheets.SheetsClient()
    missing_names = sheets_client.get_missing_names()

    twitter_client = wordlinator.twitter.TwitterClient()
    await twitter_client.notify_missing(missing_names)


def _get_day():
    parser = argparse.ArgumentParser("wordlinator")
    days = parser.add_mutually_exclusive_group()
    days.add_argument(
        "--days-ago", type=int, help="The number of days back to pull a score report."
    )
    days.add_argument(
        "--wordle-day", type=int, help="The wordle day number for the score report."
    )
    days.add_argument(
        "--date",
        type=wordlinator.utils.date_from_string,
        help="a YYYY-MM-DD format date to pull a score report.",
    )
    args = parser.parse_args()
    wordle_day = wordlinator.utils.WORDLE_TODAY
    if args.wordle_day:
        wordle_day = wordlinator.utils.WordleDay.from_wordle_no(args.wordle_day)
    elif args.days_ago:
        wordle_day = wordlinator.utils.WordleDay.from_wordle_no(
            wordle_day.wordle_no - args.days_ago
        )
    elif args.date:
        wordle_day = wordlinator.utils.WordleDay.from_date(args.date)
    return wordle_day


def load_db_scores():
    wordle_day = _get_day()
    client = wordlinator.sheets.SheetsClient(wordle_day=wordle_day)
    scores = client.get_scores()
    _save_db_scores(wordle_day, scores)


def _add_user_args():
    parser = argparse.ArgumentParser("add-user")
    parser.add_argument("username", help="The user twitter handle or name.")
    parser.add_argument(
        "--no-check-twitter",
        dest="check_twitter",
        action="store_false",
        default=True,
        help="don't check Twitter for user's scores",
    )
    parser.add_argument(
        "-g", "--games", nargs="*", help="The game/round number(s) to enroll the user."
    )
    parser.add_argument(
        "-u",
        "--unenroll-games",
        nargs="*",
        help="Game/round number(s) to unenroll the user.",
    )
    args = parser.parse_args()
    return args


async def add_user(username, games=None, unenroll_games=None, check_twitter=True):
    db = wordlinator.db.pg.WordleDb()

    user = db.get_user(username)
    if not user:
        rich.print(f"[green]Creating user {username}")
        user_id = None
        if check_twitter:
            twitter = wordlinator.twitter.TwitterClient()
            user_id = await twitter.get_user_twitter_id(username)
            if not user_id:
                check_twitter = False
                rich.print(
                    f"[yellow]No twitter ID found for {username}, "
                    "disabling twitter check"
                )
        user_id = user_id or f"{username}-NA"
        user = db.add_user(username, user_id, check_twitter=check_twitter)
    for round in games or []:
        rich.print(f"[green]Adding {username} to round {round}")
        db.add_user_to_round(username, round)
    for round in unenroll_games or []:
        rich.print(f"[green]Removing {username} from round {round}")
        db.remove_user_from_round(username, round)


def create_round():
    parser = argparse.ArgumentParser("create-round")
    parser.add_argument("round_no", type=int, help="The round number to create.")
    parser.add_argument(
        "start_date",
        type=wordlinator.utils.date_from_string,
        help="the YYYY-mm-DD format date the round starts.",
    )
    args = parser.parse_args()

    db = wordlinator.db.pg.WordleDb()
    db.get_or_create_round(args.round_no, args.start_date)
    db.create_round_holes(args.round_no)


def copy_users():
    parser = argparse.ArgumentParser("copy-users")
    parser.add_argument("from_round", type=int, help="The source round number.")
    parser.add_argument("to_round", type=int, help="The destination round.")
    args = parser.parse_args()

    wordlinator.db.pg.WordleDb().copy_players_from_round(args.from_round, args.to_round)


async def pull_gsheets_users(round_no):
    db = wordlinator.db.pg.WordleDb()
    db_users = db.get_users_by_round(round_no=round_no)

    round = db.get_or_create_round(round_no)
    wordle_day = wordlinator.utils.WordleDay.from_date(round.end_date)

    sheets = wordlinator.sheets.SheetsClient(wordle_day=wordle_day)
    sheets_users = sheets.get_users()

    for user in sheets_users:
        db_match = [u for u in db_users if u.username == user]
        if not db_match:
            rich.print(f"[yellow]Adding {user} to Round {round_no}")
            await add_user(user, games=[round_no])

    for user in db_users:
        if user.username not in sheets_users:
            rich.print(f"[yellow]Removing {user.username} from Round {round_no}")
            db.remove_user_from_round(user.username, round_no)


def sync_gsheet_users():
    parser = argparse.ArgumentParser()
    parser.add_argument("round_no", help="The round to sync.")
    args = parser.parse_args()
    asyncio.run(pull_gsheets_users(args.round_no))


def sync_add_user():
    args = _add_user_args()
    asyncio.run(
        add_user(args.username, args.games, args.unenroll_games, args.check_twitter)
    )


def sync_main():
    wordle_day = _get_day()
    asyncio.run(main(wordle_day=wordle_day))


def sync_update():
    wordle_day = _get_day()
    asyncio.run(main_update(wordle_day=wordle_day))


def sync_show_user():
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    args = parser.parse_args()
    asyncio.run(show_user(args.username))


def sync_show_missing():
    wordle_day = _get_day()
    asyncio.run(show_missing(wordle_day=wordle_day))


def sync_tweet_missing():
    asyncio.run(tweet_missing())


if __name__ == "__main__":
    sync_main()
