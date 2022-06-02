import collections

import dash

import wordlinator.db.pg as db
import wordlinator.utils

app = dash.Dash(name="WordleGolf")


def _golf_score(score_list):
    scores = [s.score for s in score_list]
    score_count = len(scores)
    score = sum(scores) - (score_count * 4)
    return score


def _get_user_scorelist(username, scores):
    scores = list(sorted(scores, key=lambda s: s.hole_id.hole))
    return {
        "Name": username,
        "Score": _golf_score(scores),
        **{f"Hole {s.hole_id.hole}": s.score for s in scores},
    }


def _format_string(col, condition):
    return "{" + col["id"] + "}" + f" {condition}"


def _column_formats(col):
    return [
        {
            "if": {
                "column_id": col["id"],
                "filter_query": _format_string(col, "> 4"),
            },
            "backgroundColor": "red",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": _format_string(col, "= 4"),
            },
            "backgroundColor": "orange",
        },
        {
            "if": {
                "column_id": col["id"],
                "filter_query": _format_string(col, "< 4"),
            },
            "backgroundColor": "green",
        },
    ]


def get_scores():
    score_list = db.WordleDb().get_scores(2)
    scores_by_user = collections.defaultdict(list)
    for score in score_list:
        scores_by_user[score.user_id.username].append(score)

    table_rows = [
        _get_user_scorelist(username, scores)
        for username, scores in scores_by_user.items()
    ]

    hole_columns = [
        {"name": f"Hole {i}", "id": f"Hole {i}", "type": "numeric"}
        for i in range(1, wordlinator.utils.WORDLE_TODAY.golf_hole.hole_no + 1)
    ]
    columns = [
        {"name": "Name", "id": "Name", "type": "text"},
        {"name": "Score", "id": "Score", "type": "text"},
        *hole_columns,
    ]

    formatting = [
        format_entry
        for column_formats in [_column_formats(col) for col in hole_columns]
        for format_entry in column_formats
    ]
    return dash.dash_table.DataTable(
        table_rows, columns, style_data_conditional=formatting, sort_action="native"
    )


app.layout = dash.html.Div(children=[dash.html.H1("#WordleGolf"), get_scores()])


server = app.server


def serve(debug=True):
    app.run_server(debug=debug)


if __name__ == "__main__":
    serve()
