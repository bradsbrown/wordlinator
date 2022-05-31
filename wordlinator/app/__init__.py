import argparse
import asyncio

import rich
import rich.table

import wordlinator.db
import wordlinator.sheets
import wordlinator.twitter
import wordlinator.utils


async def get_scores(
    wordle_day: wordlinator.utils.WordleDay = wordlinator.utils.WORDLE_TODAY,
):
    users = wordlinator.sheets.SheetsClient(wordle_day=wordle_day).get_missing_names()

    twitter_client = wordlinator.twitter.TwitterClient(wordle_day=wordle_day)

    scores = {}

    for user in users:
        user_scores = await twitter_client.get_user_wordles(user)
        day_score = [s for s in user_scores if s.wordle_day == wordle_day]
        scores[user] = day_score[0] if day_score else None
        await asyncio.sleep(1)

    return scores


def print_score_table(wordle_day, scores):
    table = rich.table.Table(
        rich.table.Column(header="Username", style="green"),
        rich.table.Column("Raw Score"),
        rich.table.Column("Golf Score"),
        rich.table.Column("Score Name"),
        title=f"Wordle Scores Day {wordle_day.wordle_no}",
    )
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
        else:
            args += ["N/A"] * 3
        table.add_row(*args)
    rich.print(table)


def _save_db_scores(wordle_day: wordlinator.utils.WordleDay, scores: dict):
    db = wordlinator.db.WordleDb()
    hole_data = wordle_day.golf_hole
    if not hole_data:
        return
    game_no = hole_data.game_no
    for user, score_list in scores.items():
        if not db.get_user(user):
            continue
        for day, score_entry in enumerate(score_list, start=1):
            db.add_score(user, game_no, day, score_entry)


async def main_update(
    wordle_day: wordlinator.utils.WordleDay = wordlinator.utils.WORDLE_TODAY,
):
    sheets_client = wordlinator.sheets.SheetsClient(wordle_day=wordle_day)

    today_scores = await get_scores(wordle_day=wordle_day)
    if not any((s is not None for s in today_scores.values())):
        raise ValueError("No scores pulled!")

    updated_scores = sheets_client.update_scores(today_scores)

    _save_db_scores(wordle_day, updated_scores)

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

    table = rich.table.Table(
        "Missing Players", title=f"Missing Wordle Scores Day {wordle_day.wordle_no}"
    )
    for name in client.get_missing_names():
        table.add_row(name)
    rich.print(table)


def _get_day():
    parser = argparse.ArgumentParser("wordlinator")
    days = parser.add_mutually_exclusive_group()
    days.add_argument(
        "--days-ago", type=int, help="The number of days back to pull a score report."
    )
    days.add_argument(
        "--wordle-day", type=int, help="The wordle day number for the score report."
    )
    args = parser.parse_args()
    wordle_day = wordlinator.utils.WORDLE_TODAY
    if args.wordle_day:
        wordle_day = wordlinator.utils.WordleDay.from_wordle_no(args.wordle_day)
    elif args.days_ago:
        wordle_day = wordlinator.utils.WordleDay.from_wordle_no(
            wordle_day.wordle_no - args.days_ago
        )
    return wordle_day


def load_db_scores():
    wordle_day = _get_day()
    client = wordlinator.sheets.SheetsClient(wordle_day=wordle_day)
    scores = client.get_scores()
    _save_db_scores(wordle_day, scores)


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


if __name__ == "__main__":
    sync_main()
