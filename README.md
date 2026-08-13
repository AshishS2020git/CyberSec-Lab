# CyberLab Phase 2 — Consent-Gated File Sharing

## Setup

Server (run on your main/host laptop):
    pip install -r server/requirements.txt
    python server/app.py

Then open http://<this-laptop-ip>:5000 in a browser.

Agent (run on each device you want to connect):
    pip install -r agent/requirements.txt
    python agent/connect.py <server-ip>

(Package agent/connect.py into connect.exe with PyInstaller if you want
a double-clickable / CLI exe: `pyinstaller --onefile connect.py`)

## What this does

- Devices running connect.exe register with the server and show up on
  the dashboard as Online/Offline.
- From the dashboard you can pick a connected device and upload a file
  to send it.
- The file does NOT just appear on the other machine. The device's
  own connect.exe terminal shows a prompt:

      >> Incoming file from server: 'notes.txt' (12KB)
         Accept this file? (y/n):

  Only typing 'y' downloads and saves it (into a `received_files`
  folder next to connect.exe). Typing 'n' discards it. The server
  never writes to the device's disk on its own.

## What this does NOT do (by design)

- No remote command execution on connected devices.
- No browsing/listing another device's filesystem.
- No transfer happens without an explicit accept on the receiving end.

## Files

    server/app.py        Flask server + dashboard + transfer queue
    server/templates/     index.html dashboard
    agent/connect.py      Source for connect.exe
