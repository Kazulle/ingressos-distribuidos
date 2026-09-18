"""Servidor HTTP concorrente para venda de assentos, usando apenas Python padrão."""
import argparse
import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


class SoldOut(Exception):
    pass


class Store:
    def __init__(self, path, capacity=50):
        if capacity < 1:
            raise ValueError("A capacidade deve ser positiva.")
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS seats (
                    number INTEGER PRIMARY KEY CHECK(number > 0)
                );
                CREATE TABLE IF NOT EXISTS purchases (
                    code TEXT PRIMARY KEY,
                    buyer TEXT NOT NULL CHECK(length(buyer) BETWEEN 1 AND 120),
                    seat INTEGER NOT NULL UNIQUE REFERENCES seats(number),
                    created_at TEXT NOT NULL
                );
            """)
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT COUNT(*) FROM seats").fetchone()[0]
            if existing == 0:
                db.executemany("INSERT INTO seats(number) VALUES (?)",
                               [(n,) for n in range(1, capacity + 1)])
            elif existing != capacity:
                raise ValueError(f"Banco existente tem {existing} assentos; use essa capacidade.")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def availability(self):
        with self.connect() as db:
            # Uma única consulta observa um único snapshot consistente.
            row = db.execute("""
                SELECT COUNT(*) AS capacity, COUNT(p.seat) AS sold,
                       COUNT(*) - COUNT(p.seat) AS available
                FROM seats s LEFT JOIN purchases p ON p.seat = s.number
            """).fetchone()
            return dict(row)

    def buy(self, buyer):
        with self.connect() as db:
            # Adquire a reserva de escrita ANTES de escolher um assento.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""
                SELECT number FROM seats
                WHERE number NOT IN (SELECT seat FROM purchases)
                ORDER BY number LIMIT 1
            """).fetchone()
            if row is None:
                raise SoldOut()
            purchase = {"code": str(uuid.uuid4()), "buyer": buyer,
                        "seat": row[0], "created_at": datetime.now(timezone.utc).isoformat()}
            db.execute("""INSERT INTO purchases(code, buyer, seat, created_at)
                          VALUES (:code, :buyer, :seat, :created_at)""", purchase)
        # O contexto fez COMMIT antes de confirmar ao cliente.
        return purchase

    def lookup(self, code):
        with self.connect() as db:
            row = db.execute("SELECT * FROM purchases WHERE code = ?", (code,)).fetchone()
            return dict(row) if row else None


def make_server(host, port, store):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def respond(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def error(self, status, code, message):
            self.respond(status, {"error": code, "message": message})

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/tickets":
                self.respond(200, store.availability())
            elif path.startswith("/purchases/"):
                purchase = store.lookup(path.removeprefix("/purchases/"))
                if purchase:
                    self.respond(200, purchase)
                else:
                    self.error(404, "not_found", "Compra não encontrada.")
            else:
                self.error(404, "not_found", "Rota não encontrada.")

        def do_POST(self):
            if urlparse(self.path).path != "/purchases":
                self.error(404, "not_found", "Rota não encontrada.")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4096:
                    raise ValueError()
                data = json.loads(self.rfile.read(size))
                buyer = data.get("buyer") if isinstance(data, dict) else None
                if not isinstance(buyer, str) or not 1 <= len(buyer.strip()) <= 120:
                    raise ValueError()
            except (ValueError, UnicodeDecodeError):
                self.error(400, "invalid_request", "Envie JSON com buyer de 1 a 120 caracteres.")
                return
            try:
                self.respond(201, store.buy(buyer.strip()))
            except SoldOut:
                self.error(409, "sold_out", "Ingressos esgotados.")
            except sqlite3.OperationalError:
                logging.exception("Falha de acesso ao banco")
                self.error(503, "unavailable", "Serviço temporariamente indisponível.")

    class Server(ThreadingHTTPServer):
        request_queue_size = 128
        daemon_threads = True

    return Server((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--capacity", type=int, default=50)
    parser.add_argument("--db", default="data/tickets.db")
    args = parser.parse_args()
    server = make_server(args.host, args.port, Store(args.db, args.capacity))
    print(f"Servidor em http://{args.host}:{server.server_port} | {args.capacity} assentos", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
