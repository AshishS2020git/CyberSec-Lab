"""
connect.py  ->  build this into connect.exe with PyInstaller.

Usage on the device you want to connect:
    connect.exe <server-ip>

What it does:
  1. Registers this device with the server dashboard.
  2. Sends a heartbeat every 5 seconds so the dashboard shows it online.
  3. Polls the server for incoming file-transfer requests addressed to
     THIS device. Nothing is downloaded automatically -- every incoming
     file is shown to the local user first, and is only saved if they
     type 'y'.

No remote command execution. No remote file browsing. This only moves
files that a human on this machine explicitly accepts.
"""

import uuid, socket, platform, getpass, time, os, sys, threading
import requests

RECEIVED_DIR = "received_files"
POLL_SECONDS = 4
HEARTBEAT_SECONDS = 5

# Keep track of transfer_ids we've already asked the user about,
# so we don't prompt twice while waiting on a slow human.
_seen_transfer_ids = set()
_lock = threading.Lock()


def get_server_from_args():
    if len(sys.argv) > 1:
        server = sys.argv[1].strip()
    else:
        server = input(
            "Server Address (e.g. 192.168.1.100:5000 or abc123.trycloudflare.com): "
        ).strip()

    # Automatically add protocol if omitted
    if not server.startswith(("http://", "https://")):

        # Cloudflare tunnels use HTTPS
        if ".trycloudflare.com" in server:
            server = "https://" + server

        # Local IPs use HTTP
        else:
            server = "http://" + server

    return server.rstrip("/")


def build_payload():
    return {
        "device_id": str(uuid.getnode()),
        "hostname": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname()),
        "os": platform.platform(),
        "username": getpass.getuser(),
    }


def heartbeat_loop(base, device_id):
    while True:
        try:
            requests.post(base + "/heartbeat", json={"device_id": device_id}, timeout=5)
        except Exception as e:
            print(f"[heartbeat error] {e}")
        time.sleep(HEARTBEAT_SECONDS)


def human_size(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.0f}TB"


def prompt_accept(filename, size):
    print()
    print(f"  >> Incoming file from server: '{filename}' ({human_size(size)})")
    while True:
        choice = input("     Accept this file? (y/n): ").strip().lower()
        if choice in ("y", "n"):
            return choice == "y"
        print("     Please type 'y' or 'n'.")


def prompt_share(path):
    print()
    print(f"  >> Server is requesting a file from this device: '{path}'")
    while True:
        choice = input("     Send it? (y/n): ").strip().lower()
        if choice in ("y", "n"):
            return choice == "y"
        print("     Please type 'y' or 'n'.")


def handle_transfer(base, t):
    transfer_id = t["transfer_id"]
    filename = t["filename"]
    size = t["size"]

    with _lock:
        if transfer_id in _seen_transfer_ids:
            return
        _seen_transfer_ids.add(transfer_id)

    accepted = prompt_accept(filename, size)

    try:
        requests.post(
            f"{base}/respond_transfer/{transfer_id}",
            json={"accepted": accepted},
            timeout=5,
        )
    except Exception as e:
        print(f"[respond error] {e}")
        return

    if not accepted:
        print(f"     Rejected '{filename}'.")
        return

    try:
        resp = requests.get(f"{base}/download_transfer/{transfer_id}", timeout=30)
        if resp.status_code != 200:
            print(f"     Could not download '{filename}' (server said {resp.status_code}).")
            return
        os.makedirs(RECEIVED_DIR, exist_ok=True)
        save_path = os.path.join(RECEIVED_DIR, filename)
        with open(save_path, "wb") as f:
            f.write(resp.content)
        print(f"     Saved to {os.path.abspath(save_path)}")
    except Exception as e:
        print(f"[download error] {e}")


def poll_loop(base, device_id):
    while True:
        try:
            resp = requests.get(f"{base}/poll_transfers/{device_id}", timeout=5)
            if resp.status_code == 200:
                for t in resp.json().get("transfers", []):
                    handle_transfer(base, t)
        except Exception as e:
            print(f"[poll error] {e}")
        time.sleep(POLL_SECONDS)


def handle_request(base, r):
    transfer_id = r["transfer_id"]
    path = r["path"]

    with _lock:
        if transfer_id in _seen_transfer_ids:
            return
        _seen_transfer_ids.add(transfer_id)

    if not os.path.isfile(path):
        print(f"\n  >> Server requested '{path}' but it doesn't exist on this device. Ignoring.")
        try:
            requests.post(f"{base}/respond_transfer/{transfer_id}", json={"accepted": False}, timeout=5)
        except Exception:
            pass
        return

    share = prompt_share(path)

    try:
        requests.post(
            f"{base}/respond_transfer/{transfer_id}",
            json={"accepted": share},
            timeout=5,
        )
    except Exception as e:
        print(f"[respond error] {e}")
        return

    if not share:
        print(f"     Did not share '{path}'.")
        return

    try:
        with open(path, "rb") as fh:
            files = {"file": (os.path.basename(path), fh)}
            resp = requests.post(f"{base}/upload_for_request/{transfer_id}", files=files, timeout=60)
        if resp.status_code == 200:
            print(f"     Sent '{path}' to the server.")
        else:
            print(f"     Server rejected the upload (status {resp.status_code}).")
    except Exception as e:
        print(f"[upload error] {e}")


def request_poll_loop(base, device_id):
    while True:
        try:
            resp = requests.get(f"{base}/poll_requests/{device_id}", timeout=5)
            if resp.status_code == 200:
                for r in resp.json().get("requests", []):
                    handle_request(base, r)
        except Exception as e:
            print(f"[request poll error] {e}")
        time.sleep(POLL_SECONDS)


def main():
    base = get_server_from_args()
    payload = build_payload()

    try:

        requests.post(base + "/register", json=payload, timeout=5)

        requests.post(base + "/trigger_refresh", timeout=2)

    except Exception as e:

        print(f"Could not reach server at {base}: {e}")

        return

    print(f"Connected to {base}. This device is now visible on the dashboard.")
    print("Waiting for file transfers you can accept or reject... (Ctrl+C to quit)")

    threading.Thread(
        target=heartbeat_loop, args=(base, payload["device_id"]), daemon=True
    ).start()

    

    threading.Thread(
    target=request_poll_loop, args=(base, payload["device_id"]), daemon=True
).start()

    try:

        poll_loop(base, payload["device_id"])

    except KeyboardInterrupt:

        print("\nDisconnecting from server...")

        try:

            requests.post(
                base + "/disconnect",
                json={"device_id": payload["device_id"]},
                timeout=5
            )

        except Exception as e:

            print(f"[disconnect error] {e}")

        print("Disconnected.")


if __name__ == "__main__":
    main()
