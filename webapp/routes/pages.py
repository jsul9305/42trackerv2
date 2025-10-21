from flask import Blueprint, render_template, request, redirect, url_for

from webapp.services.records import RecordsService

pages_bp = Blueprint('pages', __name__)


@pages_bp.route("/")
def page_index():
    return render_template("index.html", init_mid=None)

@pages_bp.route("/race/<int:mid>")
def page_race_mid(mid: int):
    return render_template("index.html", init_mid=mid)

@pages_bp.route("/race")
def page_race_qs():
    mid = request.args.get("marathon_id", type=int)
    if not mid:
        return redirect(url_for("pages.page_index"))
    return render_template("index.html", init_mid=mid)

@pages_bp.route("/admin")
def page_admin():
    return render_template("admin.html")

@pages_bp.route("/records")
def ui_records():
    q = request.args.get("q", "").strip()
    m = request.args.get("m", "").strip()
    items = RecordsService.get_all_records(query=q, marathon_filter=m)
    return render_template("records.html", items=items, q=q, m=m)
