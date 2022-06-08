import collections
import typing


def golf_score(score_list: typing.List) -> int:
    scores = [s.score for s in score_list]
    score_count = len(scores)
    score = sum(scores) - (score_count * 4)
    return score


def get_user_scorelist(
    username: str, scores: typing.List
) -> typing.Dict[str, typing.Any]:
    scores = list(sorted(scores, key=lambda s: s.hole_id.hole))
    return {
        "Name": username,
        "Score": golf_score(scores),
        **{f"Hole {s.hole_id.hole}": s.score for s in scores},
    }


def format_string(col, condition):
    return "{" + col["id"] + "}" + f" {condition}"


def column_formats(col, pct):
    return [
        {
            "if": {"column_id": col["id"]},
            "maxWidth": f"{pct}%",
            "width": f"{pct}%",
            "minWidth": f"{pct}%",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "> 4"),
            },
            "backgroundColor": "red",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "= 4"),
            },
            "backgroundColor": "orange",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "< 4"),
            },
            "backgroundColor": "green",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": format_string(col, "is nil"),
            },
            "backgroundColor": "white",
        },
    ]


def table_rows(score_list):
    scores_by_user = collections.defaultdict(list)
    for score in score_list:
        scores_by_user[score.user_id.username].append(score)

    return [
        get_user_scorelist(username, scores)
        for username, scores in scores_by_user.items()
    ]


def column_formatting(hole_columns):
    pct = round((100 - (10 + 5)) / len(hole_columns), 2)
    return [
        entry
        for format_list in [column_formats(hole, pct) for hole in hole_columns]
        for entry in format_list
    ]
