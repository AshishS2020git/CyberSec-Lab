import subprocess
import os
import tempfile

VMRUN = r"E:\VMWare\vmrun.exe"
VMX = r"E:\kali-linux-2025.2-vmware-amd64\kali-linux-2025.2-vmware-amd64.vmwarevm\kali-linux-2025.2-vmware-amd64.vmx"
USER = "kali"
PASS = "kali"
LAST_COMMAND = ""

def run_program(program, *args):
    global LAST_COMMAND
    command = [
        VMRUN,
        "-gu", USER,
        "-gp", PASS,
        "runProgramInGuest",
        VMX,
        program,
        *args
    ]
    
    if not LAST_COMMAND:
        LAST_COMMAND = " ".join([program, *args])

    print (command)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    return result.stdout.strip(), result.stderr.strip()

def get_scan_output(requires_sudo=False):

    if requires_sudo:
        guest_file = "/tmp/scan_root.txt"
    else:
        guest_file = "/tmp/scan_user.txt"

    temp_file = os.path.join(tempfile.gettempdir(), "scan.txt")

    subprocess.run([
        VMRUN,
        "-gu", USER,
        "-gp", PASS,
        "CopyFileFromGuestToHost",
        VMX,
        guest_file,
        temp_file
    ])

    if os.path.exists(temp_file):
        with open(temp_file, "r", encoding="utf-8") as f:
            return f.read()

    return "Unable to read scan output."

def get_guest_ip():
    result = subprocess.run(
        [VMRUN, "getGuestIPAddress", VMX],
        capture_output=True,
        text=True,
    )

    return result.stdout.strip(), result.stderr.strip()



def test_vm():
    result = subprocess.run(
        [VMRUN, "getGuestIPAddress", VMX],
        capture_output=True,
        text=True
    )

    return result.stdout.strip(), result.stderr.strip()

def get_last_command():
    global LAST_COMMAND

    command = LAST_COMMAND
    LAST_COMMAND = ""

    return command

def set_last_command(command):
    global LAST_COMMAND
    LAST_COMMAND = command