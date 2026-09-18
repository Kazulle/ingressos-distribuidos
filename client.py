"""Cliente separado: todas as operações passam pela rede HTTP."""
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def request(base_url, method, path, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = Request(base_url.rstrip("/") + path, data=body, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=45) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("disponibilidade")
    commands.add_parser("comprar").add_argument("comprador")
    commands.add_parser("consultar").add_argument("codigo")
    args = parser.parse_args()
    try:
        if args.command == "disponibilidade":
            status, data = request(args.url, "GET", "/tickets")
        elif args.command == "comprar":
            status, data = request(args.url, "POST", "/purchases", {"buyer": args.comprador})
        else:
            status, data = request(args.url, "GET", "/purchases/" + quote(args.codigo, safe=""))
    except (URLError, TimeoutError, OSError) as error:
        print(f"Falha de comunicação: {error}. Consulte a disponibilidade antes de tentar novamente.",
              file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if status < 400 else 1


if __name__ == "__main__":
    sys.exit(main())
