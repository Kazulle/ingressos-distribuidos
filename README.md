# Venda distribuída de ingressos

Sistema acadêmico cliente-servidor para um evento com capacidade fixa de 50 assentos.
Servidor Python com HTTP/JSON e SQLite, com transações para evitar venda duplicada.

## Servidor

Requer Python 3.11 ou superior, sem dependências externas.

```sh
python server.py
```

API: `GET /tickets`, `POST /purchases` com `{"buyer":"Maria"}` e
`GET /purchases/CODIGO`. Dados persistidos em `data/tickets.db`.
