import argparse
import json
import socket
import subprocess
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from pathlib import Path


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


def run_command(sender: Sender, command: list[str]):
    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print("Command failed, sending email", file=sys.stderr)
        sender.send("Command Failed", f"Cmd '{' '.join(command)}' failed.\n\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")


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
