from flask import Blueprint, request, jsonify
import pandas as pd
import requests
from bs4 import BeautifulSoup

from webapp.services.marathon import MarathonService
from webapp.services.participant import ParticipantService
from webapp.services.records import RecordsService
from webapp.services.group import (
    create_group,
    validate_code,
    join_group,
    get_groups_by_marathon,
    get_all_groups,
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


# -------------------- Marathons --------------------
@api_bp.route("/marathons", methods=["GET"])
def api_list_marathons_with_code():
    marathons = MarathonService.list_marathons()
    payload = [
        {
            "id": m.get("id"),
            "name": m.get("name"),
            "total_distance_km": m.get("total_distance_km"),
            "refresh_sec": m.get("refresh_sec"),
            "enabled": bool(m.get("enabled")),
            "event_date": m.get("event_date"),
            "join_code": m.get("join_code"),
            "updated_at": m.get("updated_at"),
        }
        for m in marathons
    ]
    return jsonify(payload)

@api_bp.route("/marathons", methods=["POST"])
def api_create_marathon():
    data = request.get_json(force=True) or {}
    result = MarathonService.create_marathon(**data)
    if result.get('success'):
        return jsonify(result), 201
    return jsonify({"error": result.get('error', 'Failed to create marathon')}), 400

@api_bp.route("/marathons/<int:mid>", methods=["PUT"])
def api_update_marathon(mid: int):
    data = request.get_json(force=True)
    result = MarathonService.update_marathon(mid, **data)
    if result['success']:
        return jsonify(result)
    return jsonify({"error": result.get('error', 'Failed to update marathon')}), 400

@api_bp.route("/marathons/code/<join_code>", methods=["GET"])
def api_get_marathon_by_code(join_code: str):
    m = MarathonService.get_marathon_by_join_code(join_code)
    if not m:
        return jsonify({"error": "Marathon not found for the provided join code"}), 404
    payload = {
        "id": m.get("id"),
        "name": m.get("name"),
        "total_distance_km": m.get("total_distance_km"),
        "refresh_sec": m.get("refresh_sec"),
        "enabled": bool(m.get("enabled")),
        "event_date": m.get("event_date"),
        "join_code": m.get("join_code"),
        "updated_at": m.get("updated_at"),
    }
    return jsonify(payload)

@api_bp.route("/marathons/<int:mid>/regenerate_code", methods=["POST"])
def api_regenerate_marathon_code(mid: int):
    result = MarathonService.regenerate_join_code(mid)
    if result.get('success'):
        return jsonify(result)
    return jsonify({"error": result.get('error', 'Failed to regenerate join code')}), 400

# -------------------- Groups --------------------
@api_bp.route("/groups", methods=["GET"])
def api_get_all_groups():
    groups = get_all_groups()
    return jsonify(groups)

@api_bp.route("/groups", methods=["POST"])
def api_create_group():
    data = request.get_json(force=True) or {}
    marathon_id = data.get("marathon_id")
    name = data.get("name")
    result = create_group(marathon_id, name)
    if result.get("success"):
        return jsonify(result), 201
    return jsonify({"error": result.get("error", "Failed to create group")}), 400

@api_bp.route("/groups/join", methods=["POST"])
def api_join_group():
    data = request.get_json(force=True) or {}
    join_code = data.get("join_code")
    bib_number = data.get("bib_number")
    result = join_group(join_code, bib_number)
    if result.get("success"):
        return jsonify(result), 201
    return jsonify({"error": result.get("error", "Failed to join group")}), 400


@api_bp.route("/groups/validate", methods=["POST"])
def api_validate_group_code():
    data = request.get_json(force=True) or {}
    code = (data.get("join_code") or "").strip().upper()
    if not code:
        return jsonify({"valid": False, "message": "code is required"}), 400
    result = validate_code(code)
    status = 200 if result.get("valid") else 404
    return jsonify(result), status

@api_bp.route("/marathons/<int:marathon_id>/groups", methods=["GET"])
def api_get_marathon_groups(marathon_id: int):
    groups = get_groups_by_marathon(marathon_id)
    return jsonify(groups)

@api_bp.route("/code/resolve", methods=["POST"])
def api_resolve_code():
    data = request.get_json(force=True) or {}
    code = (data.get("code") or "").strip().upper()
    if not code:
        return jsonify({"error": "Code is required"}), 400

    group_result = validate_code(code)
    if group_result["valid"]:
        return jsonify({"type": "group", "group": group_result["group"]})

    marathon = MarathonService.get_marathon_by_join_code(code)
    if marathon:
        return jsonify({"type": "marathon", "marathon": marathon})

    return jsonify({"error": "Invalid code"}), 404

# -------------------- Participants --------------------
@api_bp.route("/participants", methods=["GET"])
def api_list_participants():
    group_id = request.args.get("group_id", type=int)
    if not group_id:
        return jsonify({"error": "group_id is required"}), 400
    participants = ParticipantService.list_participants(group_id=group_id)
    return jsonify(participants)

@api_bp.route("/participants", methods=["POST"])
def api_create_participant():
    data = request.get_json(force=True)
    result = ParticipantService.create_participant(
        group_id=data.get('group_id'),
        nameorbibno=data.get('nameorbibno'),
        alias=data.get('alias')
    )
    if result['success']:
        return jsonify(result)
    return jsonify({"error": result.get('error', 'Failed to create participant')}), 400

@api_bp.route("/participants/upload_excel", methods=["POST"])
def api_upload_participants_excel():
    if 'file' not in request.files:
        return jsonify({"error": "엑셀 파일이 없습니다."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "파일을 선택해주세요."}), 400
    group_id = request.form.get('group_id', type=int)
    if not group_id:
        return jsonify({"error": "그룹 ID가 필요합니다."}), 400

    if file and (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        try:
            df = pd.read_excel(file)
            if '배번' not in df.columns or '이름' not in df.columns:
                return jsonify({"error": "엑셀 파일에 '배번'과 '이름' 컬럼이 필요합니다."}), 400

            participants_to_add = []
            for _, row in df.iterrows():
                nameorbibno = str(row['배번']).strip()
                alias = str(row['이름']).strip()
                if nameorbibno:
                    participants_to_add.append({
                        "alias": alias,
                        "nameorbibno": nameorbibno
                    })

            if not participants_to_add:
                return jsonify({"error": "추가할 참가자 데이터가 없습니다."}), 400

            result = ParticipantService.bulk_create_participants(group_id, participants_to_add)

            payload = {
                "ok": bool(result.get("success")),
                "success": bool(result.get("success")),
                "created": result.get("created", 0),
                "skipped": result.get("skipped", 0),
                "errors": result.get("errors", []),
                "message": result.get("error") if not result.get("success") else "등록 완료"
            }
            status = 200 if payload["ok"] else 400

        except Exception as e:
            payload = {
                "ok": False,
                "success": False,
                "created": 0,
                "skipped": 0,
                "errors": [f"{type(e).__name__}: {e}"],
                "message": "서버 처리 중 오류"
            }
            status = 500

        resp = jsonify(payload)
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        return resp, status
    return jsonify({"error": "지원하지 않는 파일 형식입니다."}), 400

@api_bp.route("/participants/<int:pid>", methods=["DELETE"])
def api_delete_participant(pid: int):
    result = ParticipantService.delete_participant(pid)
    if result['success']:
        return jsonify(result)
    return jsonify({"error": result.get('error', 'Failed to delete participant')}), 400

@api_bp.route("/participant_data", methods=["GET"])
def api_participant_data():
    pid = request.args.get("participant_id", type=int)
    if not pid:
        return jsonify({"error": "participant_id is required"}), 400

    data = ParticipantService.get_participant_data(pid)
    if 'error' in data:
        return jsonify(data), 404
    return jsonify(data)

@api_bp.route("/debug_participant", methods=["GET"])
def debug_participant():
    pid = request.args.get("participant_id", type=int)
    if not pid:
        return jsonify({"error": "participant_id is required"}), 400

    participant_data = ParticipantService.get_participant_data(pid)
    if 'error' in participant_data:
        return jsonify(participant_data), 404

    url = participant_data.get('url')
    if not url:
        return jsonify({"error": "Participant has no URL template"}), 400

    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        rows = []
        for tr in soup.select("table.result-table tr"):
            tds = [td.get_text(strip=True) for td in tr.select("td")]
            if len(tds) >= 4 and tds[0] != "POINT":
                rows.append(tds)
        return jsonify({"tested_url": url, "row_count": len(rows), "sample_rows": rows[:3]})
    except requests.RequestException as e:
        return jsonify({"error": f"Failed to fetch URL: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"An error occurred: {e}"}), 500
    
@api_bp.route("/records", methods=["GET"])
def api_records():
    q = request.args.get("q")
    m = request.args.get("m")
    group_id = request.args.get("group_id", type=int)
    items = RecordsService.get_all_records(query=q, marathon_filter=m, group_id=group_id)
    return jsonify({"items": items})
