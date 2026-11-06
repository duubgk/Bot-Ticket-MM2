# Bot de tickets e loja de MM2 para Discord

Bot que fiz em Python para organizar o atendimento de uma loja de itens de Murder Mystery 2 (Roblox) dentro de um servidor do Discord. O cliente abre um ticket, escolhe os itens, paga no Pix e recebe o comprovante da entrega, tudo dentro do próprio servidor.

> **Sobre como foi feito:** boa parte do código foi escrita com ajuda de IA. Eu defini o que o bot precisava fazer, testei, corrigi e fui ajustando no servidor. Estou estudando Python para entender cada parte cada vez melhor.

## O que ele faz

- **Tickets** de compra, suporte e venda de item, com canal privado para cada atendimento
- **Carrinho** para escolher itens e quantidades, com conferência do estoque
- **Pix** com código copia e cola e QR Code gerados pelo bot
- **Consulta da conta no Roblox** (nome, ID, data de criação e amigos) para confirmar o nick do cliente
- **Comprovante de entrega** em imagem, com marca d'água da loja
- **Transcript** em HTML da conversa, salvo ao fechar o ticket
- **Estoque** gerenciado por painel ou importado de um arquivo `.json`
- **Textos, cores e botões** editáveis por comando, sem mexer no código

## Como rodar

Precisa de Python 3.10 ou mais novo e de um bot criado no [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications).

```bash
pip install -r requirements.txt
```

1. Copie `.env.example` para `.env` e coloque o token do seu bot.
2. Rode o bot:

```bash
python main.py
```

3. No servidor, use `/configurar` (categoria dos tickets, cargo da equipe e canal de logs) e `/configurar_loja` (Pix e demais dados da loja).
4. Envie os painéis com `/painel` ou `/painel_suporte`.

O arquivo `settings.json` e o `estoque.json` são criados sozinhos conforme você usa os comandos. Em `estoque.exemplo.json` tem o formato para usar com `/importar_estoque`.

## Comandos

| Comando | Para que serve |
| --- | --- |
| `/configurar` | Define categoria dos tickets, cargo atendente e logs |
| `/configurar_loja` | Configura Pix, link do servidor, canal de entregas, conta do Roblox e logo |
| `/painel` e `/painel_suporte` | Enviam os painéis de tickets no canal |
| `/estoque` e `/stoq` | Gerenciar e mostrar o estoque |
| `/importar_estoque` | Importa itens de um arquivo `.json` |
| `/entregue` | Registra uma entrega e gera o comprovante |
| `/personalizar` | Edita textos, cores, imagens e botões |
| `/mensagem` | Envia uma mensagem personalizada |

## Tecnologias

Python, discord.py (componentes V2), aiohttp, Pillow, qrcode e python-dotenv.

## Segurança

O token do bot, a chave Pix e os dados da loja ficam só no seu computador (`.env`, `settings.json`). Eles estão no `.gitignore` e **não devem ser enviados para o GitHub**.
