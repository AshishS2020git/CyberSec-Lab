from kali_executor import run_program, set_last_command


def run_scan(target, scan_type, options="", sudo_password=""):

    output_file = "/tmp/scan_user.txt"
    sudo_output_file = "/tmp/scan_root.txt"

    requires_sudo = scan_type in ["-sS", "-sU", "-O", "-A"]

    if requires_sudo:

        command = (
            f'echo "{sudo_password}" | '
            f'sudo -S nmap {scan_type} {options} '
            f'-oN {sudo_output_file} {target}'
        )

        # Display this in the UI (without the password)
        set_last_command(
            f"sudo nmap {scan_type} {options} -oN {sudo_output_file} {target}"
        )

        return run_program(
            "/bin/bash",
            "-c",
            command
        )

    # Non-root scans
    set_last_command(
        f"nmap {scan_type} {options} -oN {output_file} {target}"
    )

   

    return run_program(
        "/usr/bin/nmap",
        scan_type,
        *options.split(),
        "-oN",
        output_file,
        target
    )

    