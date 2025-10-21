from flask import Blueprint, request, jsonify
import pandas as pd
import requests
from bs4 import BeautifulSoup

from webapp.services.marathon import MarathonService
from webapp.services.participant import ParticipantService
from webapp.services.records import RecordsService

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route("/marathons", methods=["GET"])
def api_list_marathons():
    marathons = MarathonService.list_marathons()
    return jsonify(marathons)

@api_bp.route("/marathons", methods=["POST"])
def api_create_marathon():
    data = request.get_json(force=True)
    result = MarathonService.create_marathon(**data)
    if result['success']:
        return jsonify(result)
    return jsonify({"error": result.get('error', 'Failed to create marathon')}), 400

@api_bp.route("/marathons/<int:mid>", methods=["PUT"])
def api_update_marathon(mid: int):
    data = request.get_json(force=True)
    result = MarathonService.update_marathon(mid, **data)
    if result['success']:
        return jsonify(result)
    return jsonify({"error": result.get('error', 'Failed to update marathon')}), 400

@api_bp.route("/participants", methods=["GET"])
def api_list_participants():
    marathon_id = request.args.get("marathon_id", type=int)
    participants = ParticipantService.list_participants(marathon_id=marathon_id)
    return jsonify(participants)

@api_bp.route("/participants", methods=["POST"])
def api_create_participant():
    data = request.get_json(force=True)
    result = ParticipantService.create_participant(
        marathon_id=data.get('marathon_id'),
        nameorbibno=data.get('nameorbibno'),
        alias=data.get('alias')
    )
    if result['success']:
        return jsonify(result)
    return jsonify({"error": result.get('error', 'Failed to create participant')}), 400

@api_bp.route("/participants/upload_excel", methods=["POST"])
def api_upload_participants_excel():
    """
    엑셀 파일로 참가자를 일괄 등록합니다.
    - form-data로 'file' (엑셀 파일)과 'marathon_id'를 받습니다.
    - 엑셀 파일에는 '배번' (nameorbibno)과 '이름' (alias) 컬럼이 있어야 합니다.
    """
    if 'file' not in request.files:
        return jsonify({"error": "엑셀 파일이 없습니다."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "파일을 선택해주세요."}), 400
    marathon_id = request.form.get('marathon_id', type=int)
    if not marathon_id:
        return jsonify({"error": "마라톤 ID가 필요합니다."}), 400

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

            result = ParticipantService.bulk_create_participants(marathon_id, participants_to_add)
            return jsonify(result)

        except Exception as e:
            return jsonify({"error": f"파일 처리 중 오류 발생: {e}"}), 500
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
    items = RecordsService.get_all_records(query=q, marathon_filter=m)
    return jsonify({"items": items})
