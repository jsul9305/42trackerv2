"""정적 파일 서빙 라우트"""

from flask import Blueprint, send_from_directory
from config.settings import STATIC_DIR

static_bp = Blueprint('static_routes', __name__)


@static_bp.route("/static/<path:filename>")
def serve_static(filename):
    """/static/ 경로의 파일을 static 폴더에서 찾아 서빙합니다."""
    return send_from_directory(STATIC_DIR, filename)