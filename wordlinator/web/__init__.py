import collections
import datetime
import functools
import time

import dash
import dash.long_callback
import diskcache
import flask
import flask.views
import plotly.graph_objs

import wordlinator.db.pg as db
import wordlinator.twitter
import wordlinator.utils
import wordlinator.utils.web

###################
# Setup Functions #
###################

app = dash.Dash(name="WordleGolf", title="#WordleGolf")


def get_ttl_hash(seconds=600):
    return round(time.time() / seconds)


cache = diskcache.Cache("./cache")
long_callback_manager = dash.long_callback.DiskcacheLongCallbackManager(
    cache, cache_by=get_ttl_hash
)


@functools.lru_cache()
def _wordle_today(ttl_hash=None):
    today = wordlinator.utils.get_wordle_today()
    if today.golf_hole:
        return today
    last_completed_round = [
        dt for dt in wordlinator.utils.WORDLE_GOLF_ROUND_DATES[::-1] if dt <= today.date
    ]
    last_round_start = last_completed_round[0]
    last_round_end = last_round_start + datetime.timedelta(days=17)
    return wordlinator.utils.WordleDay.from_date(last_round_end)


def wordle_today():
    return _wordle_today(get_ttl_hash())


@functools.lru_cache()
def _scores_from_db(ttl_hash=None):
    wordle_day = wordle_today()
    return db.WordleDb().get_scores(wordle_day.golf_hole.game_no)


def scores_from_db():
    return _scores_from_db(get_ttl_hash())


#################
# Score Helpers #
#################


def get_scores():
    score_list = scores_from_db()
    table_rows = wordlinator.utils.web.table_rows(score_list)

    hole_columns = [
        {"name": f"Hole {i}", "id": f"Hole {i}", "type": "numeric"}
        for i in range(1, wordle_today().golf_hole.hole_no + 1)
    ]
    columns = [
        {"name": "Name", "id": "Name", "type": "text"},
        {"name": "Score", "id": "Score", "type": "text"},
        *hole_columns,
    ]

    color_formatting = wordlinator.utils.web.column_formatting(hole_columns)
    formatting = [
        {"if": {"column_id": "Name"}, "textAlign": "center"},
        *color_formatting,
    ]
    return dash.dash_table.DataTable(
        table_rows,
        columns,
        style_table={
            "width": "80%",
            "margin": "auto",
            "height": "600px",
            "overflowY": "auto",
        },
        fixed_rows={"headers": True, "data": 0},
        filter_action="native",
        style_cell={"textAlign": "center"},
        style_data={"width": "10%"},
        style_as_list_view=True,
        style_data_conditional=formatting,
        sort_action="native",
    )


#################
# Stats Helpers #
#################

SCORE_NAME_MAP = {
    1: "Hole-in-1",
    2: "Eagle",
    3: "Birdie",
    4: "Par",
    5: "Bogey",
    6: "Double Bogey",
    7: "Fail",
}


def _get_score_breakdown(score, holes):
    score_row = {"Score": SCORE_NAME_MAP[score]}
    days = sorted(set(holes))
    for day in days:
        score_row[day] = holes.count(day)
    return score_row


def _get_summary_rows(score_list):
    days = list(sorted(set((score.hole_id.hole for score in score_list))))
    day_dict = {
        day: [score.score for score in score_list if score.hole_id.hole == day]
        for day in days
    }
    totals = {
        "Score": "Total",
        **{day: len(scores) for day, scores in day_dict.items()},
    }

    averages = {
        "Score": "Daily Average",
        **{
            day: round(sum(scores) / len(scores), 2) for day, scores in day_dict.items()
        },
    }

    return [totals, averages]


def _stats_dict():
    score_list = scores_from_db()

    scores_by_value = collections.defaultdict(list)
    for score in score_list:
        scores_by_value[score.score].append(score.hole_id.hole)

    table_rows = []
    for score in sorted(scores_by_value.keys()):
        table_rows.append(_get_score_breakdown(score, scores_by_value[score]))

    table_rows.extend(_get_summary_rows(score_list))
    return table_rows


def get_daily_stats():
    table_rows = _stats_dict()

    columns = [
        {"name": n, "id": n}
        for n in (
            "Score",
            *[f"{i}" for i in range(1, wordle_today().golf_hole.hole_no + 1)],
        )
    ]
    return dash.dash_table.DataTable(
        table_rows,
        columns=columns,
        style_as_list_view=True,
        style_data_conditional=[
            {"if": {"filter_query": "{Score} = 'Total'"}, "fontWeight": "bold"},
            {"if": {"filter_query": "{Score} = 'Daily Average'"}, "fontWeight": "bold"},
        ],
        style_table={"width": "80%", "margin": "auto"},
    )


#################
# Graph Helpers #
#################


SCORE_COLOR_DICT = {
    "Hole-in-1": "black",
    "Eagle": "darkgreen",
    "Birdie": "lightgreen",
    "Par": "white",
    "Bogey": "palevioletred",
    "Double Bogey": "orangered",
    "Fail": "darkred",
}


def get_line_graph():
    rows = _stats_dict()
    figure = plotly.graph_objs.Figure()
    total = [r for r in rows if r["Score"] == "Total"][0]
    rows = [r for r in rows if r["Score"] not in ("Total", "Daily Average")]
    total.pop("Score")
    for row in rows:
        score = row.pop("Score")
        y_values = []
        for k in row.keys():
            row_val = row.get(k)
            total_val = total.get(k)
            pct = row_val / total_val * 100
            y_values.append(pct)
        figure.add_trace(
            plotly.graph_objs.Scatter(
                x=list(row.keys()),
                y=y_values,
                fill="tonexty",
                name=score,
                line={"color": SCORE_COLOR_DICT[score]},
                stackgroup="dailies",
            )
        )
    figure.update_xaxes(tickvals=list(total.keys()), title_text="Days")
    figure.update_yaxes(title_text="Percent")
    figure.update_layout(yaxis_range=[0, 100])
    return dash.dcc.Graph(figure=figure)


#############
# App Setup #
#############

app.layout = dash.html.Div(
    children=[
        dash.html.H1("#WordleGolf", style={"textAlign": "center"}, id="title"),
        dash.html.Div(
            [
                dash.html.H2("User Scores", style={"textAlign": "center"}),
                dash.html.Div("Loading...", id="user-scores"),
            ]
        ),
        dash.html.Div(
            [
                dash.html.H2("Score Graph", style={"textAlign": "center"}),
                dash.html.Div("Loading...", id="stats-graph"),
            ]
        ),
        dash.html.Div(
            [
                dash.html.H2("Daily Stats", style={"textAlign": "center"}),
                dash.html.Div("Loading...", id="daily-stats"),
            ]
        ),
    ]
)


@app.long_callback(
    output=dash.dependencies.Output("user-scores", "children"),
    inputs=dash.dependencies.Input("title", "children"),
    manager=long_callback_manager,
)
def get_scores_chart(_):
    return get_scores()


@app.long_callback(
    output=dash.dependencies.Output("daily-stats", "children"),
    inputs=dash.dependencies.Input("title", "children"),
    manager=long_callback_manager,
)
def get_stats_chart(_):
    return get_daily_stats()


@app.long_callback(
    output=dash.dependencies.Output("stats-graph", "children"),
    inputs=dash.dependencies.Input("title", "children"),
    manager=long_callback_manager,
)
def get_stats_graph(_):
    return get_line_graph()


server = app.server


class GetLinkView(flask.views.View):
    methods = ["GET"]

    def dispatch_request(self):
        today = wordle_today()
        missing_users = db.WordleDb().get_users_without_score(
            today.golf_hole.game_no, today.golf_hole.hole_no
        )
        link = wordlinator.twitter.TwitterClient.full_notify_link(missing_users)
        return flask.redirect(link)


server.add_url_rule("/tweet_link", view_func=GetLinkView.as_view("tweet_link"))


def serve(debug=True):
    app.run(debug=debug)


if __name__ == "__main__":
    serve()
