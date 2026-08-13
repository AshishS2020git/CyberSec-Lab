
from flask import Flask, render_template, request, jsonify, send_file, abort, redirect, url_for, session
import sqlite3, time, os, uuid
from flask import Flask, render_template, request
from pathlib import Path
from kali_executor import *
from nmap import *
from datetime import datetime
from functools import wraps




app = Flask(__name__)
DB = "devices.db"
UPLOAD_DIR = "uploads"
app.secret_key = "NeKey1"
ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "CyberLab123"

os.makedirs(UPLOAD_DIR, exist_ok=True)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def get_con():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con



def init():
    con = get_con()
    con.execute("DROP TABLE IF EXISTS devices")
    con.execute("""CREATE TABLE IF NOT EXISTS devices(
        device_id TEXT PRIMARY KEY,
        hostname TEXT, ip TEXT, os TEXT, username TEXT,
        last_seen REAL,is_online INTEGER DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS transfers(
        transfer_id TEXT PRIMARY KEY,
        device_id TEXT,
        direction TEXT,            -- 'to_device' or 'to_server'
        filename TEXT,
        requested_path TEXT,       -- only set for 'to_server' requests
        stored_path TEXT,
        status TEXT,               -- Pending, Accepted, Rejected, Completed
        created_at REAL,
        responded_at REAL)""")
    con.execute("DELETE FROM devices")
    con.commit()
    con.close()

# ---------- Login ----------
@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("logged_in"):
        return redirect(url_for("index"))

    error = None

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:

            session["logged_in"] = True

            return redirect(url_for("index"))

        error = "Invalid username or password."

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))

# ---------- Dashboard ----------
def kali_status():

    result = get_guest_ip()

    # If get_guest_ip() returns (stdout, stderr)
    if isinstance(result, tuple):
        stdout, stderr = result
    else:
        stdout = result
        stderr = ""

    ip = stdout.strip()

    if (
        ip
        and "Error" not in ip
        and "not powered on" not in ip
        and "Unable" not in ip
        and stderr.strip() == ""
    ):
        return True, ip

    return False, stderr or ip

@app.route("/")
@login_required
def index():
    con = get_con()
    devices = con.execute(
        "SELECT device_id,hostname,ip,os,username,last_seen,is_online FROM devices"
    ).fetchall()
    transfers = con.execute(
        "SELECT transfer_id,device_id,direction,filename,status,created_at FROM transfers ORDER BY created_at DESC LIMIT 25"
    ).fetchall()
    con.close()

    

    online_devices = sum(
        1 for d in devices
        if d["is_online"] == 1
    )
    t_devices = [dict(d) for d in devices]
    for d in t_devices:
        d["last_seen_str"] = datetime.fromtimestamp(
            d["last_seen"]
        ).strftime("%d-%m-%Y %H:%M:%S")

    kali_online, kali_ip = kali_status()
    return render_template(
    "dashboard.html",
    devices=t_devices,
    online_devices=online_devices,
    transfers=transfers,
    now=time.time(),
    kali_online=kali_online,
    kali_ip=kali_ip,
    active_page="dashboard"
)

refresh_dashboard = False

@app.post("/disconnect")
def disconnect():

    device_id = request.json.get("device_id")

    if not device_id:
        return jsonify(ok=False, error="Missing device_id"), 400

    con = get_con()

    con.execute(
        """
        UPDATE devices
        SET is_online =?
        WHERE device_id=?
        """,
        (0, device_id)
    )

    con.commit()
    con.close()

    global refresh_dashboard
    refresh_dashboard = True

    return jsonify(ok=True)

@app.get("/refresh_flag")
def refresh_flag():

    global refresh_dashboard

    refresh = refresh_dashboard

    refresh_dashboard = False

    return jsonify(refresh=refresh)

@app.route("/devices/count")
def device_count():

    con = get_con()

    count = con.execute("""
        SELECT COUNT(*)
        FROM devices
        WHERE is_online = 1
    """).fetchone()[0]

    con.close()

    return jsonify({"count": count})

#---------NMAP--------#

@app.route("/nmap",methods=["GET","POST"])
def nmap_page():
    command = get_last_command()
    con=get_con()
    devices = con.execute("""
    SELECT hostname, ip
    FROM devices
    WHERE is_online = 1
    ORDER BY hostname
""").fetchall()
    return render_template(
        "nmap.html",
        devices=devices,
        output=get_scan_output(),
        command=command,
        active_page="nmap"
    )

@app.route("/scan", methods=["POST"])
def scan():

    
    target_mode = request.form["target_mode"]

    if target_mode == "configured":
        target = request.form["device_target"]
    else:
        target = request.form["manual_target"]
    

    scan_type = request.form["scan_type"]
    options = request.form["options"]

    sudo_password = request.form.get("sudo_password", "")

    requires_sudo = scan_type in ["-sS", "-sU", "-O", "-A"]

    run_scan(target, scan_type, options, sudo_password)

    nmap_output = get_scan_output(requires_sudo)
    command = get_last_command()

    con = get_con()

    devices = con.execute("""
        SELECT hostname, ip
        FROM devices
        WHERE is_online = 1
        ORDER BY hostname
    """).fetchall()

    con.close()

    return render_template(
    "nmap.html",
    devices=devices,
    output=nmap_output,
    command=command,
    active_page="nmap",

    target_source=target_mode,
    device_target=request.form.get("device_target", ""),
    manual_target=request.form.get("manual_target", ""),
    scan_type=scan_type,
    options=options
)
@app.route("/terminal")
def terminal():
    return render_template("terminal.html",active_page="terminal")

@app.route("/hydra")
def hydra():
    return render_template("hydra.html",active_page="hydra")

@app.route("/john")
def john():
    return render_template("john.html")

@app.route("/gobuster")
def gobuster():
    return render_template("gobuster.html")

@app.route("/transfers")
def transfers():
    return render_template("transfers.html")

@app.route("/logs")
def logs():
    return render_template("logs.html")


@app.post("/send_file/<device_id>")
def send_file_to_device(device_id):
    """Dashboard uploads a file here to queue it for a specific device."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(ok=False, error="No file provided"), 400

    transfer_id = str(uuid.uuid4())
    safe_name = f"{transfer_id}_{f.filename}"
    stored_path = os.path.join(UPLOAD_DIR, safe_name)
    f.save(stored_path)

    con = get_con()
    con.execute(
        "INSERT INTO transfers VALUES(?,?,?,?,?,?,?,?,?)",
        (transfer_id, device_id, "to_device", f.filename, None, stored_path,
         "pending", time.time(), None)
    )
    con.commit()
    con.close()
    return """
<script>
alert('File queued successfully');
window.location.href='/';
</script>
"""


@app.post("/request_file/<device_id>")
def request_file_from_device(device_id):
    """Dashboard asks a connected device to send a specific file path.
    The device's own connect.exe must still accept before anything uploads."""
    path = (request.form.get("path") or "").strip()
    if not path:
        return jsonify(ok=False, error="No path provided"), 400

    transfer_id = str(uuid.uuid4())
    filename = os.path.basename(path) or path

    con = get_con()
    con.execute(
        "INSERT INTO transfers VALUES(?,?,?,?,?,?,?,?,?)",
        (transfer_id, device_id, "to_server", filename, path, None,
         "pending", time.time(), None)
    )
    con.commit()
    con.close()
    return jsonify(ok=True, transfer_id=transfer_id)


@app.get("/download_completed/<transfer_id>")
def download_completed(transfer_id):
    """Dashboard downloads a file a device pushed up to the server (to_server transfers)."""
    con = get_con()
    row = con.execute(
        "SELECT stored_path, filename, direction, status FROM transfers WHERE transfer_id=?",
        (transfer_id,)
    ).fetchone()
    con.close()
    if not row or row["direction"] != "to_server" or row["status"] != "completed":
        abort(404)
    return send_file(row["stored_path"], as_attachment=True, download_name=row["filename"])


# ---------- Agent endpoints (only reachable once connect.exe is running) ----------

@app.post("/register")
def register():
    global refresh_dashboard
    d = request.json
    con = get_con()
    
    con.execute(
        "INSERT OR REPLACE INTO devices VALUES(?,?,?,?,?,?,?)",
        (d["device_id"], d["hostname"], d["ip"], d["os"], d["username"], time.time(),1)
    )
    row = con.execute(
    "SELECT device_id, is_online FROM devices WHERE device_id=?",
    (d["device_id"],)
    ).fetchone()

    print("After register:", dict(row))
    
    con.commit()
    con.close()
    refresh_dashboard = True
    return jsonify(ok=True)


@app.post("/heartbeat")
def hb():
    d = request.json
    con = get_con()
    con.execute(
        "UPDATE devices SET last_seen=? WHERE device_id=?",
        (time.time(), d["device_id"])
    )
    con.commit()
    con.close()
    return jsonify(ok=True)


@app.get("/poll_transfers/<device_id>")
def poll_transfers(device_id):
    """Agent polls this. Returns pending transfers waiting on THIS device's accept/reject
    (server -> device pushes)."""
    con = get_con()
    rows = con.execute(
        "SELECT transfer_id, filename, stored_path FROM transfers "
        "WHERE device_id=? AND direction='to_device' AND status='pending'",
        (device_id,)
    ).fetchall()
    con.close()
    result = []
    for r in rows:
        size = os.path.getsize(r["stored_path"]) if os.path.exists(r["stored_path"]) else 0
        result.append({"transfer_id": r["transfer_id"], "filename": r["filename"], "size": size})
    return jsonify(transfers=result)


@app.get("/poll_requests/<device_id>")
def poll_requests(device_id):
    """Agent polls this. Returns pending requests asking THIS device to send a file
    (device -> server pulls)."""
    con = get_con()
    rows = con.execute(
        "SELECT transfer_id, requested_path FROM transfers "
        "WHERE device_id=? AND direction='to_server' AND status='pending'",
        (device_id,)
    ).fetchall()
    con.close()
    result = [{"transfer_id": r["transfer_id"], "path": r["requested_path"]} for r in rows]
    return jsonify(requests=result)


@app.post("/upload_for_request/<transfer_id>")
def upload_for_request(transfer_id):
    """Agent calls this to actually hand over the file, only after accepting locally."""
    con = get_con()
    row = con.execute(
        "SELECT status, direction FROM transfers WHERE transfer_id=?",
        (transfer_id,)
    ).fetchone()
    if not row or row["direction"] != "to_server" or row["status"] != "accepted":
        con.close()
        abort(403)

    f = request.files.get("file")
    if not f or not f.filename:
        con.close()
        return jsonify(ok=False, error="No file provided"), 400

    safe_name = f"{transfer_id}_{f.filename}"
    stored_path = os.path.join(UPLOAD_DIR, safe_name)
    f.save(stored_path)

    con.execute(
        "UPDATE transfers SET stored_path=?, status='completed' WHERE transfer_id=?",
        (stored_path, transfer_id)
    )
    con.commit()
    con.close()
    return jsonify(ok=True)


@app.post("/respond_transfer/<transfer_id>")
def respond_transfer(transfer_id):
    """Agent calls this after the local user types y/n."""
    global refresh_dashboard
    accepted = request.json.get("accepted", False)
    con = get_con()
    con.execute(
        "UPDATE transfers SET status=?, responded_at=? WHERE transfer_id=?",
        ("Accepted" if accepted else "Rejected", time.time(), transfer_id)
    )
    con.commit()
    con.close()
    refresh_dashboard=True
    return jsonify(ok=True)


@app.get("/download_transfer/<transfer_id>")
def download_transfer(transfer_id):
    try:
        print("DOWNLOAD HIT")

        con = get_con()

        row = con.execute(
            "SELECT stored_path, filename, status FROM transfers WHERE transfer_id=?",
            (transfer_id,)
        ).fetchone()

        print("ROW:", row)

        if not row:
            print("NO ROW FOUND")
            abort(404)

        print("STATUS:", row["status"])

        if row["status"] != "accepted":
            print("NOT ACCEPTED")
            abort(403)

        print("PATH:", row["stored_path"])

        if not os.path.exists(row["stored_path"]):
            print("FILE DOES NOT EXIST")
            abort(404)

        return send_file(
            os.path.abspath(row["stored_path"]),
            as_attachment=True,
            download_name=row["filename"]
        )

    except Exception as e:
        print("DOWNLOAD ERROR:", repr(e))
        raise
@app.route("/explorer")
def explorer():
    path = request.args.get("path", str(Path.home()))

    try:
        current = Path(path)

        items = []

        if current.parent != current:
            items.append({
                "name": "..",
                "path": str(current.parent),
                "type": "parent"
            })

        for item in sorted(current.iterdir()):
            items.append({
                "name": item.name,
                "path": str(item),
                "type": "folder" if item.is_dir() else "file"
            })

        return render_template(
            "explorer.html",
            current_path=str(current),
            items=items
        )

    except Exception as e:
        return f"Error: {e}"


@app.route("/test_command")
def test_command():
    stdout, stderr = run_test()

    return {
        "stdout": stdout,
        "stderr": stderr
    }

if __name__ == "__main__":
    init()
    app.run(host="0.0.0.0", port=5000, debug=True)
