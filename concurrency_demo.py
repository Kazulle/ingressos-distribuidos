"""Dispara clientes HTTP simultâneos contra um evento vazio e verifica invariantes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from client import request


def run(url, attempts=100, workers=50):
    status, before = request(url, "GET", "/tickets")
    if status != 200 or before["sold"] != 0:
        raise ValueError("Use um evento vazio, sem outras compras durante a demonstração.")
    if attempts < before["capacity"] or not 1 <= workers <= attempts:
        raise ValueError("Tentativas devem cobrir a capacidade; workers deve estar entre 1 e tentativas.")
    barrier = Barrier(workers)

    def buy(index):
        # Sincroniza a primeira onda; cada chamada usa sua própria conexão de rede.
        if index < workers:
            barrier.wait(timeout=20)
        return request(url, "POST", "/purchases", {"buyer": f"cliente-{index + 1}"})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        responses = list(pool.map(buy, range(attempts)))
    successful = [data for code, data in responses if code == 201]
    exhausted = [data for code, data in responses if code == 409 and data.get("error") == "sold_out"]
    status, after = request(url, "GET", "/tickets")
    checks = {
        "todas as respostas são compra ou esgotamento": len(successful) + len(exhausted) == attempts,
        "vendas iguais à capacidade": len(successful) == before["capacity"],
        "assentos sem duplicatas": len({p["seat"] for p in successful}) == len(successful),
        "códigos sem duplicatas": len({p["code"] for p in successful}) == len(successful),
        "estoque final consistente": status == 200 and after == {
            "capacity": before["capacity"], "sold": before["capacity"], "available": 0},
        "todas as compras consultáveis": all(
            request(url, "GET", "/purchases/" + p["code"]) == (200, p) for p in successful),
    }
    print(f"Tentativas: {attempts} | simultâneas: {workers}")
    print(f"Compras: {len(successful)} | esgotadas: {len(exhausted)} | disponíveis: {after.get('available')}")
    for name, ok in checks.items():
        print(f"{'OK' if ok else 'FALHOU'}: {name}")
    if not all(checks.values()):
        raise AssertionError("Falha na consistência do evento.")
    return successful


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--attempts", type=int, default=100)
    parser.add_argument("--workers", type=int, default=50)
    args = parser.parse_args()
    run(args.url, args.attempts, args.workers)
