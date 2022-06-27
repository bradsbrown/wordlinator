import collections
import functools
import os
import pathlib
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
import wordlinator.utils.scores
import wordlinator.utils.web

TTL_TIME = 30 if os.getenv("DEBUG") else 90
LEADERBOARD_COUNT = 20

###################
# Setup Functions #
###################

assets_dir = pathlib.Path(__file__).parent / "assets"
app = dash.Dash(
    name="WordleGolf", title="#WordleGolf", assets_folder=str(assets_dir.resolve())
)


def get_ttl_hash(seconds=TTL_TIME):
    return round(time.time() / seconds)


cache = diskcache.Cache("./cache")
long_callback_manager = dash.long_callback.DiskcacheLongCallbackManager(
    cache, cache_by=get_ttl_hash
)


@functools.lru_cache(maxsize=1)
def _games_from_db(ttl_hash=None):
    return db.WordleDb().get_rounds()


def games_from_db():
    return _games_from_db()


@functools.lru_cache(maxsize=1)
def _wordle_today(ttl_hash=None):
    today = wordlinator.utils.get_wordle_today()
    if today.golf_hole:
        return today
    last_completed_round = [
        game for game in games_from_db()[::-1] if game.start_date <= today.date
    ]
    last_round = last_completed_round[0]
    return wordlinator.utils.WordleDay.from_date(last_round.end_date)


def wordle_today():
    return _wordle_today(get_ttl_hash())


def round_wordle_day(round_id):
    wt = wordle_today()
    rounds = games_from_db()

    matching_round = [r for r in rounds if r.game_id == round_id][0]
    if matching_round.game == wt.golf_hole.game_no:
        return wt
    return wordlinator.utils.WordleDay.from_date(matching_round.end_date)


@functools.lru_cache(maxsize=3)
def _scores_from_db(round_id, ttl_hash=None):
    wordle_db = db.WordleDb()
    scores = wordle_db.get_scores(round_id=round_id)
    users = wordle_db.get_users_by_round(round_id=round_id)
    usernames = [u.username for u in users]
    return wordlinator.utils.scores.ScoreMatrix(scores, usernames=usernames)


def scores_from_db(round_id):
    return _scores_from_db(round_id)


#######################
# Leaderboard helpers #
#######################


def get_leaderboard(round_id):
    score_matrix = scores_from_db(round_id)
    user_scores = score_matrix.by_user()
    top_20 = dict(
        list(sorted(user_scores.items(), key=lambda u: u[1].golf_score))[
            :LEADERBOARD_COUNT
        ]
    )
    return dash.dash_table.DataTable(
        [{"Name": k, "Score": v.golf_score} for k, v in top_20.items()],
        style_as_list_view=True,
        style_table={"width": "40%", "margin": "auto"},
        style_cell={"textAlign": "center"},
    )


#################
# Score Helpers #
#################


def get_scores(round_id):
    score_matrix = scores_from_db(round_id)
    round_day = round_wordle_day(round_id)
    table_rows = score_matrix.user_rows(round_day)

    hole_columns = [
        {"name": f"{i}", "id": f"{i}", "type": "text", "presentation": "markdown"}
        for i in range(1, round_day.golf_hole.hole_no + 1)
    ]
    columns = [
        {"name": "Name", "id": "Name", "type": "text"},
        {"name": "Score", "id": "Score", "type": "text"},
        *hole_columns,
    ]

    color_formatting = wordlinator.utils.web.column_formatting(hole_columns)
    formatting = [
        {
            "if": {"column_id": "Name"},
            "textAlign": "center",
            "width": "10%",
            "maxWidth": "10%",
            "minWidth": "10%",
        },
        {
            "if": {"column_id": "Score"},
            "textAlign": "center",
            "width": "5%",
            "maxWidth": "5%",
            "minWidth": "5%",
        },
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
        filter_options={"case": "insensitive"},
        style_cell={"textAlign": "center"},
        style_data={"width": "10%"},
        style_as_list_view=True,
        style_data_conditional=formatting,
        sort_action="native",
    )


#################
# Stats Helpers #
#################


def _get_summary_rows(score_matrix):
    day_dict = score_matrix.by_hole()

    totals = {
        "Score": "Total",
        **{day: scores.count for day, scores in day_dict.items()},
    }

    averages = {
        "Score": "Daily Average",
        **{day: scores.average for day, scores in day_dict.items()},
    }

    return [totals, averages]


def _stats_dict(round_id):
    score_matrix = scores_from_db(round_id)
    table_rows = [{"Score": k, **v} for k, v in score_matrix.score_breakdown().items()]
    table_rows.extend(_get_summary_rows(score_matrix))
    return table_rows


def get_daily_stats(round_id):
    table_rows = _stats_dict(round_id)

    columns = [
        {"name": n, "id": n}
        for n in (
            "Score",
            *[
                f"{i}"
                for i in range(1, round_wordle_day(round_id).golf_hole.hole_no + 1)
            ],
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


def get_line_graph(round_id):
    rows = _stats_dict(round_id)
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


#####################
# Line Race Helpers #
#####################


def line_race_graph(round_id):
    score_matrix = scores_from_db(round_id)
    tops_by_day = score_matrix.top_by_day()
    round_day = round_wordle_day(round_id)
    hole_no = round_day.golf_hole.hole_no

    figure = plotly.graph_objs.Figure()
    figure.update_yaxes(autorange="reversed")
    figure.update_xaxes(tickmode="linear", tick0=1, dtick=1)
    annotation_names = collections.defaultdict(list)
    for name, entries in tops_by_day.items():
        figure.add_trace(
            plotly.graph_objs.Scatter(
                name=name,
                mode="lines+markers",
                x=[e[0] for e in entries],
                y=[e[1] for e in entries],
            )
        )
        if entries[-1][0] == hole_no:
            annotation_names[entries[-1]].append(name)

    annotations = [
        {"x": k[0], "y": k[1], "text": ", ".join(v)}
        for k, v in annotation_names.items()
    ]
    figure.update_layout(annotations=annotations)
    return dash.dcc.Graph(figure=figure)


#############
# App Setup #
#############

app.layout = dash.html.Div(
    children=[
        dash.html.H1("#WordleGolf", style={"textAlign": "center"}, id="title"),
        dash.html.Div(
            wordlinator.utils.web.get_date_dropdown(
                games_from_db(), wordle_day=wordle_today()
            ),
            id="round-selector",
            style={"maxWidth": "300px"},
        ),
        dash.dcc.Tabs(
            id="main-tabs",
            value="leaderboard",
            children=[
                dash.dcc.Tab(label="Leaderboard", value="leaderboard"),
                dash.dcc.Tab(label="Statistics", value="statistics"),
                dash.dcc.Tab(label="User Scores", value="user-scores"),
            ],
        ),
        dash.dcc.Loading(dash.html.Div(id="tab-content"), id="tab-content-loading"),
    ]
)


@app.callback(
    dash.dependencies.Output("tab-content", "children"),
    [
        dash.dependencies.Input("main-tabs", "value"),
        dash.dependencies.Input("round-selector-dropdown", "value"),
    ],
)
def render_tab(tab, round_id):
    if tab == "leaderboard":
        return [
            dash.html.Div(
                [
                    dash.html.H2(
                        f"Leaderboard - Top {LEADERBOARD_COUNT}",
                        style={"textAlign": "center"},
                    ),
                    dash.dcc.Loading(
                        id="leaderboard-race-loading",
                        children=dash.html.Div(
                            line_race_graph(round_id), id="leaderboard-race"
                        ),
                    ),
                    dash.dcc.Loading(
                        id="leaderboard-loading",
                        children=dash.html.Div(
                            get_leaderboard(round_id), id="leaderboard"
                        ),
                    ),
                ]
            ),
        ]
    elif tab == "user-scores":
        return [
            dash.html.Div(
                [
                    dash.html.H2("User Scores", style={"textAlign": "center"}),
                    dash.dcc.Loading(
                        id="user-scores-loading",
                        children=dash.html.Div(get_scores(round_id), id="user-scores"),
                    ),
                ]
            ),
        ]
    elif tab == "statistics":
        return [
            dash.html.Div(
                [
                    dash.html.H2("Score Graph", style={"textAlign": "center"}),
                    dash.dcc.Loading(
                        id="stats-graph-loading",
                        children=dash.html.Div(
                            get_line_graph(round_id), id="stats-graph"
                        ),
                    ),
                ]
            ),
            dash.html.Div(
                [
                    dash.html.H2("Daily Stats", style={"textAlign": "center"}),
                    dash.dcc.Loading(
                        id="daily-stats-loading",
                        children=dash.html.Div(
                            get_daily_stats(round_id), id="daily-stats"
                        ),
                    ),
                ]
            ),
        ]


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
