import json
import sqlite3
import subprocess
import sys
import tempfile
import uuid
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from client import request
from concurrency_demo import run
from server import Store, make_server


class SystemTests(unittest.TestCase):
    def setUp(self):
        # mkdir padrão mantém ACLs herdadas também em ambientes Windows restritos.
        self.temp = Path(tempfile.gettempdir()) / ("ingressos-test-" + uuid.uuid4().hex)
        self.temp.mkdir()
        self.path = self.temp / "tickets.db"
        self.store = Store(self.path, 50)
        self.server = make_server("127.0.0.1", 0, self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        for file in self.temp.iterdir():
            file.unlink()
        self.temp.rmdir()

    def test_concurrent_network_purchases(self):
        purchases = run(self.url)
        self.assertEqual(len(purchases), 50)
        self.assertEqual(request(self.url, "POST", "/purchases", {"buyer": "extra"})[0], 409)

    def test_validation_and_missing_purchase(self):
        for payload in ({}, {"buyer": "  "}, {"buyer": 42}, {"buyer": "x" * 121}, [], None):
            self.assertEqual(request(self.url, "POST", "/purchases", payload)[0], 400)
        req = Request(self.url + "/purchases", data=b"{bad json", method="POST")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 400)
        ctx.exception.close()
        self.assertEqual(request(self.url, "GET", "/purchases/inexistente")[0], 404)
        self.assertEqual(request(self.url, "GET", "/inexistente")[0], 404)
        self.assertEqual(self.store.availability()["available"], 50)

    def test_persistence_capacity_and_database_constraints(self):
        status, purchase = request(self.url, "POST", "/purchases", {"buyer": "João"})
        self.assertEqual(status, 201)
        reopened = Store(self.path, 50)
        self.assertEqual(reopened.lookup(purchase["code"]), purchase)
        self.assertEqual(reopened.availability()["available"], 49)
        with self.assertRaises(ValueError):
            Store(self.path, 51)
        for seat in (purchase["seat"], 999):
            with self.assertRaises(sqlite3.IntegrityError):
                with reopened.connect() as db:
                    db.execute("INSERT INTO purchases VALUES (?, ?, ?, ?)",
                               (f"duplicate-{seat}", "Outro", seat, "agora"))

    def test_separate_client_process(self):
        result = subprocess.run([sys.executable, "client.py", "--url", self.url,
                                 "comprar", "Maria"], capture_output=True, text=True,
                                encoding="utf-8", timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        purchase = json.loads(result.stdout)
        self.assertEqual(request(self.url, "GET", "/purchases/" + purchase["code"]), (200, purchase))


if __name__ == "__main__":
    unittest.main()
