import argparse
import json
import socket
import subprocess
import sys
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from pathlib import Path
from typing import IO


class Sender:
    def __init__(self, host: str, smtp_host: str, smtp_port: int, user: str, password: str, from_: str, to: str):
        self.host = host
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.user = user
        self.password = password
        self.from_ = from_
        self.to = to

    def send(self, subject: str, body: str):
        msg = MIMEMultipart()
        msg['From'] = self.from_
        msg['To'] = self.to
        msg['Subject'] = "{}: {}".format(self.host, subject)
        msg.attach(MIMEText("{}\n{}".format(self.host, body), "plain"))

        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.starttls()
        server.login(self.user, self.password)
        text = msg.as_string()
        server.sendmail(self.from_, self.to, text)
        server.quit()


class StreamThread(threading.Thread):
    def __init__(self, stream: IO[bytes], out_stream: IO[bytes]):
        super().__init__(daemon=True)
        self._stream = stream
        self._out_stream = out_stream
        self.captured = b""

    def run(self):
        while True:
            line = self._stream.readline(16 * 1024)
            if not line:
                break
            self._out_stream.write(line)
            self._out_stream.flush()
            self.captured += line


def run_command(sender: Sender, command: list[str]):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout_thread = StreamThread(stream=process.stdout, out_stream=sys.stdout.buffer)
    stderr_thread = StreamThread(stream=process.stderr, out_stream=sys.stderr.buffer)
    stdout_thread.start()
    stderr_thread.start()

    exit_code = process.wait()

    stdout_thread.join()
    stderr_thread.join()

    if exit_code != 0:
        print(f"\n\n--Command failed, exit code {exit_code}, sending email", file=sys.stderr)
        try:
            stdout = stdout_thread.captured.decode()
        except UnicodeDecodeError as err:
            stdout = f">>>Error decoding stdout ({err})<<<<\n\nbinary:\n{stdout_thread.captured}"
        try:
            stderr = stderr_thread.captured.decode()
        except UnicodeDecodeError as err:
            stderr = f">>>>Error decoding stderr ({err})<<<<\n\nbinary:\n{stderr_thread.captured}"
        sender.send(
            "Command Failed",
            f"Cmd '{' '.join(command)}' exit code {exit_code}.\n\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}",
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="The command to run")
    args = parser.parse_args()
    command = args.command
    if len(command) == 0:
        parser.error("No command")
    if command[0] == '--':
        command = command[1:]
    if len(command) == 0:
        parser.error("No command")
    with open(args.config_file) as f:
        config = json.load(f)

    sender = Sender(
        host=socket.gethostname(),
        smtp_host=config["smtp_host"],
        smtp_port=config["smtp_port"],
        user=config["user"],
        password=config["password"],
        from_=config["from"],
        to=config["to"],
    )

    run_command(sender, command)


if __name__ == "__main__":
    main()
