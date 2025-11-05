import time
from datetime import datetime, timedelta
from flask import Flask, Response, request, redirect, url_for
import copy

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
            # (point, net_time, pace, interval)
            ("5K", "00:25:10", "05:02", "00:25:10"),
            ("10K", "00:50:30", "05:04", "00:25:20"),
            ("20K", "01:41:00", "05:03", "00:50:30"),
            ("Finish", "03:35:00", "05:05", "01:54:00"),
        ]
    },
    ("spct", "202"): {
        "name": "박분석",
        "bib": "202",
        "splits": [
            ("5K", "00:30:00", "6:00", "00:30:00"),
            ("10K", "01:00:00", "6:00", "00:30:00"),
            ("Half", "02:15:00", "6:24", "01:15:00"),
            ("30K", "03:05:00", "6:40", "00:50:00"),
            ("Finish", "04:20:00", "6:10", "01:15:00"),
        ]
    },
    ("smartchip", "303"): {
        "name": "이칩",
        "bib": "303",
        "splits": [
            # (point, net_time, pace) - no interval for smartchip
            ("5K", "00:28:00", "5:36"),
            ("10K", "00:58:00", "6:00"),
            ("20K", "02:00:00", "6:10"),
            ("30K", "03:05:00", "6:30"),
            ("Finish", "04:15:00", "6:20"),
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
            "total_splits": len(data["splits"])
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
        
    current_splits = get_current_splits_for_runner("myresult", bib)
    
    rows_html = ""
    base_time = datetime.now()
    for i, split in enumerate(current_splits):
        point, net_time, pace, interval = split
        # The parser expects: point, clock, interval, net_time.
        # We generate a fake clock time as the parser needs it.
        pass_clock = (base_time + timedelta(minutes=i*30)).strftime('%H:%M:%S')

        rows_html += f"""
        <div class="table-row ant-row">
          <div class="ant-col">{point}</div>
          <div class="ant-col">{pass_clock}</div>
          <div class="ant-col">{interval}</div>
          <div class="ant-col">{net_time}</div>
        </div>
        """

    return f"""
    <html><head><title>MyResult Mock</title><meta http-equiv="refresh" content="5"></head><body>
        <div class="td-name">{runner_info['name']}</div>
        <div class="td-num">{runner_info['bib']}</div>
        {rows_html}
    </body></html>
    """

def render_spct_html(bib):
    runner_key = ("spct", bib)
    runner_info = FULL_RACE_DATA.get(runner_key)
    if not runner_info:
        return "Runner not found", 404
        
    current_splits = get_current_splits_for_runner("spct", bib)
    
    rows_html = ""
    base_time = datetime.now()
    for i, split in enumerate(current_splits):
        point, net_time, pace, interval = split
        pass_clock = (base_time + timedelta(minutes=i*30)).strftime('%H:%M:%S')
        rows_html += f"""
        <tr>
            <td>{point}</td>
            <td>{pass_clock}</td>
            <td>{net_time}</td>
            <td>{pace}</td>
            <td>{interval}</td>
        </tr>
        """

    return f"""
    <html><head><title>SPCT Mock</title><meta http-equiv="refresh" content="5"></head><body>
        <div id="bib">{runner_info['bib']}</div>
        <div id="name">{runner_info['name']}</div>
        <table id="result_list">
            <tbody>{rows_html}</tbody>
        </table>
    </body></html>
    """

def render_smartchip_html(bib):
    runner_key = ("smartchip", bib)
    runner_info = FULL_RACE_DATA.get(runner_key)
    if not runner_info:
        return "Runner not found", 404
        
    current_splits = get_current_splits_for_runner("smartchip", bib)
    
    rows_html = ""
    base_time = datetime.now()
    for i, split in enumerate(current_splits):
        point, net_time, pace = split
        pass_clock = (base_time + timedelta(minutes=i*30)).strftime('%H:%M:%S')
        rows_html += f"""
        <tr>
            <td>{point}</td>
            <td>{pass_clock}</td>
            <td>{net_time}</td>
            <td>{pace}</td>
        </tr>
        """

    return f"""
    <html><head><title>SmartChip Mock</title><meta http-equiv="refresh" content="5"></head><body>
        <table>
            <tr><td class="result_bib">{runner_info['bib']}</td></tr>
            <tr><td class="result_name">{runner_info['name']}</td></tr>
        </table>
        <table class="result_table">
            <tbody>{rows_html}</tbody>
        </table>
    </body></html>
    """

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
        if ACTIVE_RUNNERS_STATE[runner_key]['visible_splits'] < ACTIVE_RUNNERS_STATE[runner_key]['total_splits']:
            ACTIVE_RUNNERS_STATE[runner_key]['visible_splits'] += 1
    return redirect(url_for('runner_control_page', site_type=site_type, bib=bib))

@app.route("/reset_runner/<site_type>/<bib>", methods=['POST'])
def reset_runner(site_type, bib):
    """Resets a single runner's splits to 0."""
    runner_key = (site_type, bib)
    if runner_key in ACTIVE_RUNNERS_STATE:
        ACTIVE_RUNNERS_STATE[runner_key]['visible_splits'] = 0
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
        generic_splits = [
            ("5K", "00:30:00", "06:00", "00:30:00"),
            ("10K", "01:05:00", "06:30", "00:35:00"),
            ("Finish", "02:15:00", "07:00", "01:10:00"),
        ]
        if site_type == 'smartchip':
             generic_splits = [
                ("5K", "00:30:00", "6:00"),
                ("10K", "01:05:00", "6:30"),
                ("Finish", "02:15:00", "7:00"),
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
            "total_splits": len(generic_splits)
        }
    return redirect(url_for('admin_index'))


# --- 5. Original Mock Routes (Modified) ---

@app.route("/myresult/<path:subpath>")
def mock_myresult(subpath):
    bib = subpath.split('/')[-1]
    html = render_myresult_html(bib)
    return Response(html, mimetype='text/html')

@app.route("/spct/<path:subpath>")
def mock_spct(subpath):
    bib = subpath.split('/')[-1]
    html = render_spct_html(bib)
    return Response(html, mimetype='text/html')

@app.route("/smartchip/<path:subpath>")
def mock_smartchip(subpath):
    bib = subpath.split('/')[-1]
    html = render_smartchip_html(bib)
    return Response(html, mimetype='text/html')

if __name__ == "__main__":
    reset_all_runners() # Initialize the state when the server starts
    print("Full mock server for crawler testing running on http://localhost:5002")
    app.run(port=5002, debug=True)
