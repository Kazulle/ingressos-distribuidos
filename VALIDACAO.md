# Registro de validação

Executado em Windows em 17/09/2026, com Python e a biblioteca padrão.

Comando: `python -m unittest discover -s tests -v`.

Resultado: **4 testes aprovados**.

| Cenário | Resultado |
|---|---|
| 100 tentativas HTTP, até 50 clientes simultâneos | 50 compras e 50 respostas de esgotamento |
| Assentos e códigos retornados | Sem duplicatas |
| Estoque final | 0 disponíveis, 50 vendidos |
| Consulta dos 50 códigos | Todas corresponderam às compras originais |
| Compra após esgotamento | HTTP 409 |
| JSON e compradores inválidos | HTTP 400, sem consumir estoque |
| Código inexistente | HTTP 404 |
| Reabertura do banco | Compra preservada |
| Mudança de capacidade de banco existente | Rejeitada |
| Inserção direta de assento duplicado ou inexistente | Rejeitada pelo banco |
| Cliente executado em processo separado | Compra e consulta corretas |

Saída da demonstração executada pelos testes:

```text
Tentativas: 100 | simultâneas: 50
Compras: 50 | esgotadas: 50 | disponíveis: 0
OK: todas as respostas são compra ou esgotamento
OK: vendas iguais à capacidade
OK: assentos sem duplicatas
OK: códigos sem duplicatas
OK: estoque final consistente
OK: todas as compras consultáveis
```

Docker não está instalado no ambiente de validação. Os arquivos Dockerfile e
Compose foram preparados, mas a construção e execução dos contêineres não foram
validadas aqui. O teste de rede executado usa o servidor HTTP real em uma thread;
há também um teste específico que executa o cliente em outro processo.
