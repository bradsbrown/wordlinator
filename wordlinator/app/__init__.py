import asyncio
import datetime

import rich
import rich.table

import wordlinator.sheets
import wordlinator.twitter

WORDLE_DAY_ONE = datetime.date(2021, 6, 20)
WORDLE_TODAY_NUMBER = (datetime.date.today() - WORDLE_DAY_ONE).days


async def get_scores(wordle_day=WORDLE_TODAY_NUMBER):
    users = wordlinator.sheets.get_wordlegolf_users()

    twitter_client = wordlinator.twitter.TwitterClient()

    scores = {}

    for user in users:
        user_scores = await twitter_client.get_user_wordles(user)
        day_score = [s for s in user_scores if s.wordle_no == wordle_day]
        scores[user] = day_score[0] if day_score else None

    return scores


async def main():
    wordle_day = WORDLE_TODAY_NUMBER  # - 1
    scores = await get_scores(wordle_day)

    table = rich.table.Table(
        rich.table.Column(header="Username", style="green"),
        rich.table.Column("Raw Score"),
        rich.table.Column("Golf Score"),
        rich.table.Column("Score Name"),
        title=f"Wordle Scores Day {wordle_day}",
    )
    for username, score in scores.items():
        args = [username]
        if score:
            raw_score = score.raw_score
            if raw_score < 4:
                color = "green"
            elif raw_score == 4:
                color = "white"
            elif raw_score > 6:
                color = "red"
            else:
                color = "blue"

            score_args = [raw_score, score.score, score.score_name]
            args += [f"[{color}]{arg}" for arg in score_args]
        else:
            args += ["N/A"] * 3
        table.add_row(*args)
    rich.print(table)


def sync_main():
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
