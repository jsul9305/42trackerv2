import time
from datetime import datetime, timedelta
from flask import Flask, Response, request, redirect, url_for, jsonify, render_template
import copy

# --- 0. CSS --- (for the admin page)
ADMIN_CSS = """
:root{
    --bg:#0b0f17; --card:#111827; --muted:#9ca3af; --text:#e5e7eb;
    --accent:#22c55e; --accent2:#60a5fa; --warn:#f59e0b; --danger:#ef4444;
    --border:#1f2937;
}
*{box-sizing:border-box}
body{margin:0; background:var(--bg); color:var(--text);
    font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;}
a{color:#93c5fd; text-decoration:none}
.wrap{max-width:1100px; margin:0 auto; padding:16px 16px 80px 16px;}

.btn{display:inline-flex; align-items:center; justify-content:center; gap:8px;
    padding:10px 14px; border-radius:12px; border:1px solid var(--border);
    background:#0f1624; color:var(--text); font-weight:700; cursor:pointer}
.btn.primary{background:#111b2d; border-color:#274060}

.card{background:var(--card); border:1px solid var(--border); border-radius:16px; padding:14px;
    box-shadow:0 4px 10px rgba(0,0,0,.25);}
.card h3{margin:0 0 8px; font-size:16px}

table { border-collapse: collapse; width: 100%; margin-top: 12px; }
tr { border-bottom: 1px solid var(--border); }
th, td { border: 0; padding: 10px; text-align: left; }
thead th { background-color: var(--card); font-size: 12px; color: var(--muted); }

.form-container { margin-top: 20px; padding: 20px; border-radius: 16px; background-color: var(--card); border:1px solid var(--border); }
.form-container h2 { margin: 0 0 12px; }
.field{display:flex; flex-direction:column; gap:4px; flex:1;}
.field label{font-size:12px; color:var(--muted)}
.input, select{ padding:12px; border-radius:12px; border:1px solid var(--border); background:#0f1624; color:var(--text); width:100%; font-size:14px; }
.row{display:flex; gap:8px; flex-wrap:wrap; align-items:flex-end}
"""

# --- 1. Flask App Setup ---
app = Flask(__name__)

# --- 2. Data Store & Simulation Logic ---

# Base data for runners. This is the "full" data.
# Standardized split labels to match GPX processing: 5K, 10K, Half, Finish etc.
FULL_RACE_DATA = {
    # Key: (site_type, bib)
    ("myresult", "101"): {
        "name": "김결과",
        "bib": "101",
        "splits": [
            ("Start", "00:00:00", "00:00:00"),
            ("5K", "00:25:10", "00:25:10"),
            ("10K", "00:50:30", "00:25:20"),
            ("15K", "01:16:00", "00:25:30"),
            ("20K", "01:41:00", "00:25:00"),
            ("25K", "02:06:30", "00:25:30"),
            ("30K", "02:32:00", "00:25:30"),
            ("35K", "02:58:00", "00:26:00"),
            ("40K", "03:24:00", "00:26:00"),
            ("Finish", "03:35:00", "00:11:00"),
        ]
    },
    ("spct", "202"): {
        "name": "박분석",
        "bib": "202",
        "splits": [
            ("Start", "00:00:00", "0:00", "00:00:00"),
            ("5K", "00:30:00", "6:00", "00:30:00"),
            ("10K", "01:00:00", "6:00", "00:30:00"),
            ("15K", "01:30:00", "6:00", "00:30:00"),
            ("20K", "02:00:00", "6:00", "00:30:00"),
            ("25K", "02:35:00", "7:00", "00:35:00"),
            ("30K", "03:10:00", "7:00", "00:35:00"),
            ("35K", "03:45:00", "7:00", "00:35:00"),
            ("40K", "04:20:00", "7:00", "00:35:00"),
            ("Finish", "04:35:00", "7:30", "00:15:00"),
        ]
    },
    ("smartchip", "303"): {
        "name": "이칩",
        "bib": "303",
        "splits": [
            ("Start", "00:00:00", "0:00"),
            ("5K", "00:28:00", "5:36"),
            ("10K", "00:58:00", "6:00"),
            ("15K", "01:28:00", "6:00"),
            ("20K", "02:00:00", "6:24"),
            ("25K", "02:32:00", "6:24"),
            ("30K", "03:05:00", "6:36"),
            ("35K", "03:40:00", "7:00"),
            ("40K", "04:15:00", "7:00"),
            ("Finish", "04:30:00", "7:30"),
        ]
    },
    ("smartchip", "404"): {
        "name": "나모그",
        "bib": "404",
        "splits": [
            ("Start", "00:00:00", "0:00"),
            ("5K", "00:28:00", "5:36"),
            ("10K", "00:58:00", "6:00"),
            ("15K", "01:28:00", "6:00"),
            ("20K", "02:00:00", "6:24"),
            ("25K", "02:32:00", "6:24"),
            ("30K", "03:05:00", "6:36"),
            ("35K", "03:40:00", "7:00"),
            ("40K", "04:15:00", "7:00"),
            ("45K", "04:50:00", "7:00"),
            ("50K", "05:25:00", "7:00"),
            ("Finish", "05:40:00", "7:30"),
        ]
    },
    ("myresult", "1157"): {
        "name": "가mock",
        "bib": "1157",
        "splits": [
            ("Start", "00:00:00", "00:00:00"),
            ("5K", "00:21:22", "00:21:22"),
            ("10K", "00:42:21", "00:20:59"),
            ("15K", "01:03:40", "00:21:19"),
            ("20K", "01:24:40", "00:21:00"),
            ("25K", "01:45:48", "00:21:08"),
            ("30K", "02:07:57", "00:22:09"),
            ("35K", "02:37:04", "00:29:07"),
            ("40K", "03:09:51", "00:32:47"),
            ("Finish", "03:24:08", "00:14:17"),
        ]
    },
}

# Active state of our runners. We'll modify this dictionary.
# It will store how many splits are currently visible for each runner.
ACTIVE_RUNNERS_STATE = {}

def reset_all_runners():
    """Resets the state of all runners to 0 splits."""
    global ACTIVE_RUNNERS_STATE
    for key, data in FULL_RACE_DATA.items():
        ACTIVE_RUNNERS_STATE[key] = {
            "name": data["name"],
            "bib": data["bib"],
            "site_type": key[0],
            "visible_splits": 0,
            "total_splits": len(data["splits"]),
            "split_pass_times": {}
        }

def get_current_splits_for_runner(site_type, bib):
    """Gets the currently visible splits for a runner based on the state."""
    runner_key = (site_type, bib)
    state = ACTIVE_RUNNERS_STATE.get(runner_key)
    if not state:
        return None
    
    full_splits = FULL_RACE_DATA[runner_key]["splits"]
    return full_splits[:state["visible_splits"]]

# --- 3. HTML Templates ---

def render_myresult_html(bib):
    runner_key = ("myresult", bib)
    runner_info = FULL_RACE_DATA.get(runner_key)
    if not runner_info:
        return "Runner not found", 404
        
    state = ACTIVE_RUNNERS_STATE.get(runner_key)
    if not state:
        return "Runner state not found", 404

    all_splits_data = runner_info["splits"]
    visible_splits_count = state["visible_splits"]
    pass_times = state.get("split_pass_times", {})
    
    splits_for_template = []
    for i, split_data in enumerate(all_splits_data):
        point, net_time, interval = split_data
        
        if i < visible_splits_count:
            pass_time_obj = pass_times.get(i)
            pass_clock = pass_time_obj.strftime('%H:%M:%S') if pass_time_obj else "N/A"
            splits_for_template.append({
                "point": point,
                "pass_clock": pass_clock,
                "interval": interval,
                "net_time": net_time
            })
        else:
            splits_for_template.append({
                "point": point,
                "pass_clock": "-",
                "interval": "-",
                "net_time": "-"
            })

    return render_template("mock_myresult.html", runner_info=runner_info, splits=splits_for_template)

def render_spct_html(bib):
    runner_key = ("spct", bib)
    runner_info = FULL_RACE_DATA.get(runner_key)
    if not runner_info:
        return "Runner not found", 404
        
    state = ACTIVE_RUNNERS_STATE.get(runner_key)
    if not state:
        return "Runner state not found", 404

    visible_splits_count = state["visible_splits"]
    pass_times = state.get("split_pass_times", {})
    
    visible_splits_data = runner_info["splits"][:visible_splits_count]
    splits_for_template = []
    for i, split_data in enumerate(visible_splits_data):
        point, net_time, pace, interval = split_data
        pass_time_obj = pass_times.get(i)
        pass_clock = pass_time_obj.strftime('%H:%M:%S') if pass_time_obj else "N/A"
        splits_for_template.append({
            "point": point,
            "pass_clock": pass_clock,
            "net_time": net_time,
            "pace": pace,
            "interval": interval
        })

    return render_template("mock_spct.html", runner_info=runner_info, splits=splits_for_template)

def render_smartchip_html(bib):
    runner_key = ("smartchip", bib)
    runner_info = FULL_RACE_DATA.get(runner_key)
    if not runner_info:
        return "Runner not found", 404
        
    state = ACTIVE_RUNNERS_STATE.get(runner_key)
    if not state:
        return "Runner state not found", 404

    all_splits_data = runner_info["splits"]
    visible_splits_count = state["visible_splits"]
    pass_times = state.get("split_pass_times", {})
    
    splits_for_template = []
    for i, split_data in enumerate(all_splits_data):
        point, net_time, pace = split_data
        
        if i < visible_splits_count:
            pass_time_obj = pass_times.get(i)
            pass_clock = pass_time_obj.strftime('%H:%M:%S') if pass_time_obj else "N/A"
            splits_for_template.append({
                "point": point,
                "pass_clock": pass_clock,
                "net_time": net_time,
                "pace": pace
            })
        else:
            splits_for_template.append({
                "point": point,
                "pass_clock": "-",
                "net_time": "-",
                "pace": "-"
            })

    return render_template("mock_smartchip.html", runner_info=runner_info, splits=splits_for_template)

# --- 4. New Interactive Routes ---

@app.route("/")
def admin_index():
    """Main page to control the mock server."""
    
    runners_html = ""
    for (site_type, bib), state in sorted(ACTIVE_RUNNERS_STATE.items()):
        runners_html += f"""
        <tr>
            <td>{site_type}</td>
            <td>{state['name']} ({bib})</td>
            <td>{state['visible_splits']} / {state['total_splits']}</td>
            <td>
                <a href="/runner/{site_type}/{bib}" target="_blank">제어 페이지</a>
            </td>
            <td>
                <form action="/reset_runner/{site_type}/{bib}" method="post" style="display:inline;">
                    <button type="submit">리셋</button>
                </form>
            </td>
        </tr>
        """

    return f"""
    <html>
        <head>
            <title>Mock Server Control</title>
            <style>
                body {{ font-family: sans-serif; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .container {{ padding: 20px; max-width: 800px; margin: auto; }}
                .form-container {{ margin-top: 20px; padding: 15px; border: 1px solid #ccc; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Mock Server Control</h1>
                <p>이 페이지에서 목업 사용자를 제어할 수 있습니다. '제어 페이지'를 열어 기록을 수동으로 추가하세요.</p>
                <table>
                    <thead>
                        <tr>
                            <th>사이트 타입</th>
                            <th>사용자 (배번)</th>
                            <th>현재 기록 수</th>
                            <th>액션</th>
                            <th>리셋</th>
                        </tr>
                    </thead>
                    <tbody>
                        {runners_html}
                    </tbody>
                </table>
                
                <div class="form-container">
                    <h2>새 사용자 추가</h2>
                    <form action="/add_runner" method="post">
                        <label for="site_type">사이트 타입:</label>
                        <select name="site_type" id="site_type">
                            <option value="myresult">myresult</option>
                            <option value="spct">spct</option>
                            <option value="smartchip">smartchip</option>
                        </select>
                        <label for="bib">배번:</label>
                        <input type="text" name="bib" required>
                        <label for="name">이름:</label>
                        <input type="text" name="name" required>
                        <button type="submit">사용자 추가</button>
                    </form>
                </div>

                <form action="/reset_all" method="post" style="margin-top: 20px;">
                    <button type="submit">모든 사용자 리셋</button>
                </form>
            </div>
        </body>
    </html>
    """

@app.route("/runner/<site_type>/<bib>")
def runner_control_page(site_type, bib):
    """Page to control a single runner's splits."""
    runner_key = (site_type, bib)
    state = ACTIVE_RUNNERS_STATE.get(runner_key)
    if not state:
        return "Runner not found", 404

    crawl_url = f"http://localhost:5002/{site_type}/record/{bib}"

    return f"""
    <html>
        <head>
            <title>Control for {state['name']}</title>
            <meta http-equiv="refresh" content="10">
            <style>
                body {{ font-family: sans-serif; padding: 20px; }}
                .info {{ margin-bottom: 20px; }}
                .action-btn {{ font-size: 1.5em; padding: 10px 20px; }}
            </style>
        </head>
        <body>
            <h1>{state['name']} ({bib}) 제어</h1>
            <div class="info">
                <p><strong>크롤링 대상 URL:</strong> <a href="{crawl_url}" target="_blank">{crawl_url}</a></p>
                <p><strong>현재 기록:</strong> {state['visible_splits']} / {state['total_splits']}</p>
            </div>
            <form action="/add_split/{site_type}/{bib}" method="post">
                <button class="action-btn" type="submit">다음 기록 추가</button>
            </form>
        </body>
    </html>
    """

@app.route("/add_split/<site_type>/<bib>", methods=['POST'])
def add_split(site_type, bib):
    """Increments the visible split count for a runner."""
    runner_key = (site_type, bib)
    if runner_key in ACTIVE_RUNNERS_STATE:
        state = ACTIVE_RUNNERS_STATE[runner_key]
        if state['visible_splits'] < state['total_splits']:
            # Record pass time for the new split before incrementing
            # The index of the new split is the current number of visible splits
            new_split_index = state['visible_splits']
            if new_split_index not in state['split_pass_times']:
                state['split_pass_times'][new_split_index] = datetime.now()
            
            state['visible_splits'] += 1
    return redirect(url_for('runner_control_page', site_type=site_type, bib=bib))

@app.route("/remove_split/<site_type>/<bib>", methods=['POST'])
def remove_split(site_type, bib):
    """Decrements the visible split count for a runner."""
    runner_key = (site_type, bib)
    if runner_key in ACTIVE_RUNNERS_STATE:
        if ACTIVE_RUNNERS_STATE[runner_key]['visible_splits'] > 0:
            ACTIVE_RUNNERS_STATE[runner_key]['visible_splits'] -= 1
    return redirect(url_for('runner_control_page', site_type=site_type, bib=bib))

@app.route("/reset_runner/<site_type>/<bib>", methods=['POST'])
def reset_runner(site_type, bib):
    """Resets a single runner's splits to 0."""
    runner_key = (site_type, bib)
    if runner_key in ACTIVE_RUNNERS_STATE:
        ACTIVE_RUNNERS_STATE[runner_key]['visible_splits'] = 0
        ACTIVE_RUNNERS_STATE[runner_key]['split_pass_times'] = {}
    return redirect(url_for('admin_index'))

@app.route("/reset_all", methods=['POST'])
def reset_all():
    """Resets all runners."""
    reset_all_runners()
    return redirect(url_for('admin_index'))

@app.route("/add_runner", methods=['POST'])
def add_runner():
    site_type = request.form['site_type']
    bib = request.form['bib']
    name = request.form['name']
    runner_key = (site_type, bib)

    if runner_key not in FULL_RACE_DATA:
        # Create some generic data for the new runner
        if site_type == 'myresult':
            generic_splits = [
                ("Start", "00:00:00", "00:00:00"),
                ("5K", "00:30:00", "00:30:00"),
                ("10K", "01:00:00", "00:30:00"),
                ("15K", "01:30:00", "00:30:00"),
                ("20K", "02:00:00", "00:30:00"),
                ("25K", "02:30:00", "00:30:00"),
                ("30K", "03:00:00", "00:30:00"),
                ("35K", "03:30:00", "00:30:00"),
                ("40K", "04:00:00", "00:30:00"),
                ("Finish", "04:15:00", "00:15:00"),
            ]
        elif site_type == 'smartchip':
             generic_splits = [
                ("Start", "00:00:00", "0:00"),
                ("5K", "00:30:00", "6:00"),
                ("10K", "01:00:00", "6:00"),
                ("15K", "01:30:00", "6:00"),
                ("20K", "02:00:00", "6:00"),
                ("25K", "02:30:00", "6:00"),
                ("30K", "03:00:00", "6:00"),
                ("35K", "03:30:00", "6:00"),
                ("40K", "04:00:00", "6:00"),
                ("Finish", "04:15:00", "7:30"),
            ]
        else: # spct
            generic_splits = [
                ("Start", "00:00:00", "0:00", "00:00:00"),
                ("5K", "00:30:00", "6:00", "00:30:00"),
                ("10K", "01:00:00", "6:00", "00:30:00"),
                ("15K", "01:30:00", "6:00", "00:30:00"),
                ("20K", "02:00:00", "6:00", "00:30:00"),
                ("25K", "02:30:00", "6:00", "00:30:00"),
                ("30K", "03:00:00", "6:00", "00:30:00"),
                ("35K", "03:30:00", "6:00", "00:30:00"),
                ("40K", "04:00:00", "6:00", "00:30:00"),
                ("Finish", "04:15:00", "7:30", "00:15:00"),
            ]

        FULL_RACE_DATA[runner_key] = {
            "name": name,
            "bib": bib,
            "splits": generic_splits
        }
        ACTIVE_RUNNERS_STATE[runner_key] = {
            "name": name,
            "bib": bib,
            "site_type": site_type,
            "visible_splits": 0,
            "total_splits": len(generic_splits),
            "split_pass_times": {}
        }
    return redirect(url_for('admin_index'))


@app.route("/api/runner/<site_type>/<bib>")
def api_runner_data(site_type, bib):
    runner_key = (site_type, bib)
    runner_info = FULL_RACE_DATA.get(runner_key)
    if not runner_info:
        return jsonify({"error": "Runner not found"}), 404

    state = ACTIVE_RUNNERS_STATE.get(runner_key)
    if not state:
        return jsonify({"error": "Runner state not found"}), 404

    # Get all splits, not just visible ones, to have a full list on the frontend
    all_splits = runner_info["splits"]
    
    # Add current time as 'pass_time' to all splits
    now = datetime.now()
    splits_with_passtime = []
    for i, split in enumerate(all_splits):
        point, net_time, interval = split
        # Simulate increasing pass time for mockup. Each split is 5 minutes after the previous.
        pass_time = (now + timedelta(minutes=i*5)).strftime('%H:%M:%S')
        splits_with_passtime.append((point, pass_time, interval, net_time))

    data = {
        "name": runner_info["name"],
        "bib": runner_info["bib"],
        "site_type": site_type,
        "visible_splits": state["visible_splits"],
        "total_splits": state["total_splits"],
        "splits": splits_with_passtime
    }
    return jsonify(data)


# --- 5. Original Mock Routes (Modified) ---

@app.route("/myresult/<path:subpath>")
def mock_myresult(subpath):
    bib = subpath.split('/')[-1]
    return render_myresult_html(bib)

@app.route("/spct/<path:subpath>")
def mock_spct(subpath):
    bib = subpath.split('/')[-1]
    return render_spct_html(bib)

@app.route("/smartchip/<path:subpath>")
def mock_smartchip(subpath):
    bib = subpath.split('/')[-1]
    return render_smartchip_html(bib)

@app.route("/return_data_livephoto.asp")
def mock_smartchip_new():
    nameorbibno = request.args.get('nameorbibno')
    
    # Find the runner by name or bib
    runner_key = None
    for key, data in FULL_RACE_DATA.items():
        if key[0] == 'smartchip' and (data['name'] == nameorbibno or data['bib'] == nameorbibno):
            runner_key = key
            break
            
    if not runner_key:
        return "Runner not found", 404
        
    bib = runner_key[1]
    return render_smartchip_html(bib)

if __name__ == "__main__":
    reset_all_runners() # Initialize the state when the server starts
    print("Full mock server for crawler testing running on http://localhost:5002")
    app.run(port=5002, debug=True)
