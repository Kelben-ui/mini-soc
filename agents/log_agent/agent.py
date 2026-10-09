import time
import requests
import threading

COLLECTOR_URL = "http://127.0.0.1:9000/ingest"

LOG_FILES = {
    "/var/log/nginx/access.log": "nginx_access",
    "/var/log/auth.log": "auth",
    "/var/log/mini_soc_ids.json": "mini_soc_ids",
}


def watch_log(log_file, log_type):
    with open(log_file, "r") as f:
        f.seek(0, 2)

        while True:
            line = f.readline()

            if not line:
                time.sleep(1)
                continue

            try:
                response = requests.post(
                    COLLECTOR_URL,
                    json={
                        "log_type": log_type,
                        "raw": line.strip()
                    },
                    timeout=5
                )

                print(
                    f"{log_type} log sent: "
                    f"{response.status_code} "
                    f"{response.text}"
                )

            except Exception as e:
                print(f"{log_type} error: {e}")


for log_file, log_type in LOG_FILES.items():
    thread = threading.Thread(
        target=watch_log,
        args=(log_file, log_type),
        daemon=True
    )
    thread.start()


while True:
    time.sleep(60)
