import asyncio
import html
import io
import json
import os
import re
import time
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

COR_PADRAO = 0x5865F2
SETTINGS_ARQUIVO = Path("settings.json")
ESTOQUE_ARQUIVO = Path("estoque.json")

# --- Configurações padrão (dá pra mudar tudo por comando) ---
DEFAULTS = {
    "ids": {"categoria": 0, "categoria_suporte": 0, "cargo": 0, "logs": 0, "dm": True},
    "painel_msg": [0, 0],
    "painel_suporte_msg": [0, 0],
    "menu_suporte": {
        "placeholder": "Selecione o tipo de atendimento...",
        "opcoes": {
            "suporte": {"label": "Suporte", "descricao": "Falar com a staff do servidor", "emoji": "🎧"},
            "venda": {"label": "Vender item de MM2", "descricao": "Quero vender um item", "emoji": "💰"},
        },
    },
    "containers": {
        "painel": {
            "titulo": "🛒 Loja de MM2",
            "texto": (
                "Bem-vindo à nossa loja!\n"
                "Clique em **Comprar MM2** para abrir um ticket ou veja o que temos em "
                "**Estoque Disponível**."
            ),
            "cor": "#5865F2",
            "imagem": "",
        },
        "estoque": {
            "titulo": "📦 Estoque Disponível",
            "texto": "",
            "cor": "#5865F2",
            "imagem": "",
        },
        "boas_vindas": {
            "titulo": "🎫 Bem-vindo ao seu ticket!",
            "texto": (
                "Olá {usuario}! Seu ticket foi aberto com sucesso.\n"
                "Por favor, **aguarde** que um atendente ({cargo}) virá te atender em breve."
            ),
            "cor": "#57F287",
            "imagem": "",
        },
        "info_ticket": {
            "titulo": "📋 Informações do ticket",
            "texto": (
                "**Aberto por:** {usuario} (`{id}`)\n"
                "**Item de interesse:** {item}\n"
                "**Nick informado:** `{nick}`\n"
                "**Aberto em:** {data}"
            ),
            "cor": "#FEE75C",
            "imagem": "",
        },
        "roblox": {
            "titulo": "🎮 Conta do Roblox",
            "texto": (
                "**Usuário:** [{nome}]({link})\n"
                "**Nome de exibição:** {display}\n"
                "**ID:** `{id}`\n"
                "**Conta criada:** {criado}\n"
                "**Amigos:** {amigos}"
            ),
            "cor": "#E2231A",
            "imagem": "",
        },
        "painel_suporte": {
            "titulo": "🎧 Central de Atendimento",
            "texto": (
                "Precisa de ajuda ou quer vender um item de MM2?\n"
                "Escolha uma opção no menu abaixo para abrir um ticket."
            ),
            "cor": "#5865F2",
            "imagem": "",
        },
        "boas_vindas_suporte": {
            "titulo": "🎧 Suporte",
            "texto": (
                "Olá {usuario}! Seu ticket de suporte foi aberto.\n"
                "**Aguarde** que um atendente ({cargo}) virá te ajudar em breve."
            ),
            "cor": "#5865F2",
            "imagem": "",
        },
        "info_suporte": {
            "titulo": "📋 Informações do ticket",
            "texto": (
                "**Aberto por:** {usuario} (`{id}`)\n"
                "**Assunto:** {assunto}\n"
                "**Aberto em:** {data}"
            ),
            "cor": "#FEE75C",
            "imagem": "",
        },
        "boas_vindas_venda": {
            "titulo": "💰 Venda de item",
            "texto": (
                "Olá {usuario}! Recebemos o seu pedido de venda.\n"
                "**Aguarde** que um atendente ({cargo}) virá avaliar o seu item."
            ),
            "cor": "#57F287",
            "imagem": "",
        },
        "info_venda": {
            "titulo": "📋 Informações da venda",
            "texto": (
                "**Aberto por:** {usuario} (`{id}`)\n"
                "**Item à venda:** {item}\n"
                "**Preço desejado:** {preco}\n"
                "**Nick informado:** `{nick}`\n"
                "**Aberto em:** {data}"
            ),
            "cor": "#FEE75C",
            "imagem": "",
        },
    },
    "botoes": {
        "comprar": {"label": "Comprar MM2", "emoji": "🛒", "estilo": "success"},
        "estoque": {"label": "Estoque Disponível", "emoji": "📦", "estilo": "primary"},
        "fechar": {"label": "Fechar ticket", "emoji": "🔒", "estilo": "danger"},
    },
    "secoes": {
        "godlys": "🔪 Godlys",
        "sets": "🎁 Sets",
        "vazio": "*Nenhum item disponível no momento.*",
    },
    "loja": {
        "nome": "Mystic Store",
        "pix_chave": "",
        "pix_nome": "",
        "pix_cidade": "SAO PAULO",
        "link_servidor": "",
        "canal_entregas": 0,
        "roblox_loja": "",
        "proof": 1000,
    },
    "roblox_erro": (
        "⚠️ Não encontrei o usuário `{nick}` no Roblox. "
        "O atendente vai conferir o nick com você."
    ),
}

# Informações de cada container para o painel /personalizar
CONTAINERS = {
    "painel": {
        "nome": "🛒 Painel principal",
        "vars": "nenhuma",
        "h": "#",
        "obs": "Os botões não aparecem na prévia. Ao salvar, o painel já enviado é atualizado.",
    },
    "estoque": {
        "nome": "📦 Estoque (público)",
        "vars": "nenhuma",
        "h": "#",
        "obs": "As listas de Godlys e Sets aparecem sozinhas abaixo do texto.",
    },
    "boas_vindas": {
        "nome": "🎫 Boas-vindas (compra)",
        "vars": "{usuario} {cargo}",
        "h": "#",
        "obs": "Vale para os próximos tickets abertos.",
    },
    "info_ticket": {
        "nome": "📋 Info do ticket (compra)",
        "vars": "{usuario} {id} {item} {nick} {data}",
        "h": "##",
        "obs": "Vale para os próximos tickets abertos.",
    },
    "roblox": {
        "nome": "🎮 Conta do Roblox",
        "vars": "{nome} {display} {id} {criado} {amigos} {link} {nick}",
        "h": "##",
        "obs": "O avatar do Roblox aparece sozinho ao lado do texto. Aparece nos tickets de compra e venda.",
    },
    "painel_suporte": {
        "nome": "🎧 Painel de suporte/venda",
        "vars": "nenhuma",
        "h": "#",
        "obs": "O menu aparece abaixo do texto. Ao salvar, o painel já enviado é atualizado.",
    },
    "boas_vindas_suporte": {
        "nome": "🎧 Boas-vindas (suporte)",
        "vars": "{usuario} {cargo}",
        "h": "#",
        "obs": "Vale para os próximos tickets de suporte.",
    },
    "info_suporte": {
        "nome": "📋 Info do ticket (suporte)",
        "vars": "{usuario} {id} {assunto} {data}",
        "h": "##",
        "obs": "Vale para os próximos tickets de suporte.",
    },
    "boas_vindas_venda": {
        "nome": "💰 Boas-vindas (venda)",
        "vars": "{usuario} {cargo}",
        "h": "#",
        "obs": "Vale para os próximos tickets de venda.",
    },
    "info_venda": {
        "nome": "📋 Info da venda",
        "vars": "{usuario} {id} {item} {preco} {nick} {data}",
        "h": "##",
        "obs": "Vale para os próximos tickets de venda.",
    },
}

# Tipos de ticket: prefixo do nome do canal e containers usados
TIPOS_TICKET = {
    "compra": {"prefixo": "ticket", "containers": ("boas_vindas", "info_ticket")},
    "suporte": {"prefixo": "suporte", "containers": ("boas_vindas_suporte", "info_suporte")},
    "venda": {"prefixo": "venda", "containers": ("boas_vindas_venda", "info_venda")},
}

BOTOES_NOMES = {"comprar": "Comprar MM2", "estoque": "Estoque Disponível", "fechar": "Fechar ticket"}
ESTILOS = {"azul": "primary", "cinza": "secondary", "verde": "success", "vermelho": "danger"}
ESTILOS_INV = {v: k for k, v in ESTILOS.items()}

# Valores de exemplo usados na prévia
VARS_EXEMPLO = {
    "usuario": "@Usuário",
    "cargo": "@Atendente",
    "id": "123456789",
    "item": "Harvester",
    "nick": "NickDoRoblox",
    "data": "hoje às 20:00",
    "nome": "NickDoRoblox",
    "display": "Nome de Exibição",
    "criado": "01/01/2018",
    "amigos": "25",
    "link": "https://www.roblox.com",
    "assunto": "Preciso de ajuda com uma troca",
    "preco": "R$ 20,00",
}


# --- Salvar e carregar as configurações ---
def mesclar(base: dict, novo: dict) -> None:
    for k, v in novo.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            mesclar(base[k], v)
        else:
            base[k] = v


def carregar_settings() -> dict:
    dados = deepcopy(DEFAULTS)
    if SETTINGS_ARQUIVO.exists():
        mesclar(dados, json.loads(SETTINGS_ARQUIVO.read_text(encoding="utf-8")))
    return dados


def salvar_settings() -> None:
    SETTINGS_ARQUIVO.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


cfg = carregar_settings()


def carregar_estoque() -> dict:
    if not ESTOQUE_ARQUIVO.exists():
        return {"godlys": [], "sets": []}
    dados = json.loads(ESTOQUE_ARQUIVO.read_text(encoding="utf-8"))
    dados.setdefault("godlys", [])
    dados.setdefault("sets", [])
    # itens que ficaram em "pistolas"/"facas" (versão anterior) voltam para godlys
    for antiga in ("pistolas", "facas"):
        dados["godlys"].extend(dados.pop(antiga, []))
    return dados


def salvar_estoque(dados: dict) -> None:
    ESTOQUE_ARQUIVO.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def categorias():
    return (("godlys", cfg["secoes"]["godlys"]), ("sets", cfg["secoes"]["sets"]))


intents = discord.Intents.default()
intents.message_content = True  # necessário para o transcript ler o texto das mensagens
bot = commands.Bot(command_prefix="!", intents=intents)


# --- Funções de apoio ---
def estilo(nome: str) -> discord.ButtonStyle:
    return getattr(discord.ButtonStyle, nome, discord.ButtonStyle.primary)


def parse_cor(txt, padrao: int = COR_PADRAO) -> int:
    try:
        return int(str(txt).strip().lstrip("#"), 16)
    except ValueError:
        return padrao


def cor_valida(txt: str) -> bool:
    t = txt.strip().lstrip("#")
    if len(t) != 6:
        return False
    try:
        int(t, 16)
        return True
    except ValueError:
        return False


def emoji_valido(txt: str) -> bool:
    if not txt:
        return True
    if txt.startswith("<") and txt.endswith(">"):
        return True
    return len(txt) <= 8 and not any(ch.isascii() and ch.isalnum() for ch in txt)


class _Seguro(dict):
    def __missing__(self, chave):
        return "{" + chave + "}"


def formatar(texto: str, variaveis: dict) -> str:
    """Troca {variaveis} no texto. Se algo estiver errado, devolve o texto como está."""
    try:
        return texto.format_map(_Seguro(variaveis))
    except Exception:
        return texto


def eh_staff(membro: discord.Member) -> bool:
    return membro.guild_permissions.administrator or any(
        r.id == cfg["ids"]["cargo"] for r in membro.roles
    )


def dividir_blocos(conteudo: str) -> list:
    # Uma linha com só --- vira uma linha separadora entre dois blocos de texto
    blocos, atual = [], []
    for linha in conteudo.split("\n"):
        if linha.strip() == "---":
            blocos.append("\n".join(atual).strip())
            atual = []
        else:
            atual.append(linha)
    blocos.append("\n".join(atual).strip())
    blocos = [b for b in blocos if b]
    return blocos or ["(sem texto)"]


def banner(url: str):
    if url:
        return [discord.ui.MediaGallery(discord.MediaGalleryItem(url))]
    return []


def criar_botao(chave: str, custom_id: Optional[str] = None) -> discord.ui.Button:
    b = cfg["botoes"][chave]
    return discord.ui.Button(
        label=b["label"],
        emoji=b["emoji"] or None,
        style=estilo(b["estilo"]),
        custom_id=custom_id,
    )


def montar_container(chave: str, variaveis: dict, miniatura: Optional[str] = None):
    """Monta um container (V2) a partir do que foi configurado por comando."""
    d = cfg["containers"][chave]
    nivel = CONTAINERS[chave]["h"]
    titulo = formatar(d["titulo"], variaveis)
    texto = formatar(d["texto"], variaveis)
    conteudo = (f"{nivel} {titulo}\n" if titulo else "") + texto
    if not conteudo.strip():
        conteudo = "(sem texto)"

    c = discord.ui.Container(accent_colour=parse_cor(d["cor"]))
    blocos = dividir_blocos(conteudo)
    primeiro = discord.ui.TextDisplay(blocos[0])
    if miniatura:
        c.add_item(discord.ui.Section(primeiro, accessory=discord.ui.Thumbnail(miniatura)))
    else:
        c.add_item(primeiro)
    for extra in blocos[1:]:
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay(extra))
    for item in banner(d["imagem"]):
        c.add_item(item)
    return c


def linha_estoque(item: dict) -> str:
    """Uma linha no estilo: - ( emoji ) `8 un. Nome - R$ 17,49`"""
    emoji_txt, nome = separar_emoji(item["nome"])
    prefixo = f"( {emoji_txt} ) " if emoji_txt else ""
    return f"- {prefixo}`{item['qtd']} un. {nome} - {moeda(preco_para_float(item['preco']))}`"


def linhas_estoque(itens: list) -> str:
    # do mais caro pro mais barato; para antes de estourar o limite do Discord
    linhas, tamanho = [], 0
    for item in sorted(itens, key=lambda i: preco_para_float(i["preco"]), reverse=True):
        linha = linha_estoque(item)
        if tamanho + len(linha) > 3800:
            break
        linhas.append(linha)
        tamanho += len(linha) + 1
    return "\n".join(linhas)


def container_estoque() -> discord.ui.Container:
    dados = carregar_estoque()
    c = montar_container("estoque", {})
    mostrou = False
    for chave, titulo in categorias():
        disponiveis = [i for i in dados[chave] if i["qtd"] > 0]
        if not disponiveis:
            continue  # sem item disponível nessa seção: não mostra a seção
        mostrou = True
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay(f"## {titulo}\n{linhas_estoque(disponiveis)}"))
    if not mostrou:
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay(cfg["secoes"]["vazio"]))
    return c


async def atualizar_painel(qual: str = "painel"):
    """Atualiza o painel já enviado no canal ('painel' ou 'painel_suporte'), se existir."""
    canal_id, msg_id = cfg["painel_msg" if qual == "painel" else "painel_suporte_msg"]
    if not (canal_id and msg_id):
        return
    try:
        canal = bot.get_channel(canal_id) or await bot.fetch_channel(canal_id)
        msg = await canal.fetch_message(msg_id)
        await msg.edit(view=PainelView() if qual == "painel" else PainelSuporteView())
    except Exception as e:
        print(f"[Painel] não consegui atualizar: {e}")


def resetar(chave: str) -> None:
    cfg["containers"][chave] = deepcopy(DEFAULTS["containers"][chave])
    if chave == "estoque":
        cfg["secoes"] = deepcopy(DEFAULTS["secoes"])
    elif chave == "roblox":
        cfg["roblox_erro"] = DEFAULTS["roblox_erro"]
    elif chave == "painel":
        cfg["botoes"]["comprar"] = deepcopy(DEFAULTS["botoes"]["comprar"])
        cfg["botoes"]["estoque"] = deepcopy(DEFAULTS["botoes"]["estoque"])
    elif chave == "boas_vindas":
        cfg["botoes"]["fechar"] = deepcopy(DEFAULTS["botoes"]["fechar"])
    elif chave == "painel_suporte":
        cfg["menu_suporte"] = deepcopy(DEFAULTS["menu_suporte"])
    salvar_settings()


async def buscar_roblox(nick: str):
    """Busca dados públicos da conta no Roblox. Devolve None se não achar."""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [nick], "excludeBannedUsers": False},
            ) as r:
                achados = (await r.json()).get("data", [])
            if not achados:
                return None
            uid = achados[0]["id"]

            async with s.get(f"https://users.roblox.com/v1/users/{uid}") as r:
                perfil = await r.json()

            avatar = None
            async with s.get(
                "https://thumbnails.roblox.com/v1/users/avatar-headshot",
                params={"userIds": uid, "size": "150x150", "format": "Png"},
            ) as r:
                lista = (await r.json()).get("data", [])
                if lista:
                    avatar = lista[0].get("imageUrl")

            async with s.get(f"https://friends.roblox.com/v1/users/{uid}/friends/count") as r:
                amigos = (await r.json()).get("count", "?")

        criado = datetime.strptime(perfil["created"][:19], "%Y-%m-%dT%H:%M:%S")
        criado = int(criado.replace(tzinfo=timezone.utc).timestamp())
        return {
            "id": uid,
            "nome": perfil.get("name", nick),
            "display": perfil.get("displayName", nick),
            "criado": criado,
            "amigos": amigos,
            "banido": perfil.get("isBanned", False),
            "avatar": avatar,
            "link": f"https://www.roblox.com/users/{uid}/profile",
        }
    except Exception as e:
        print(f"[Roblox] erro ao buscar '{nick}': {e}")
        return None


# --- Transcript (arquivo HTML, não precisa de host) ---
def texto_componentes(componentes) -> list:
    partes = []
    try:
        for c in componentes:
            conteudo = getattr(c, "content", None)
            if isinstance(conteudo, str):
                partes.append(conteudo)
            for filho in getattr(c, "children", None) or []:
                partes.extend(texto_componentes([filho]))
    except Exception:
        pass
    return partes


async def gerar_transcript(canal: discord.TextChannel) -> bytes:
    blocos = []
    async for m in canal.history(limit=None, oldest_first=True):
        partes = []
        if m.content:
            partes.append(m.content)
        partes += texto_componentes(m.components)
        texto = html.escape("\n".join(partes)).replace("\n", "<br>")
        anexos = "".join(
            f'<div><a href="{html.escape(a.url)}">📎 {html.escape(a.filename)}</a></div>'
            for a in m.attachments
        )
        hora = m.created_at.strftime("%d/%m/%Y %H:%M")
        blocos.append(
            f'<div class="msg"><img src="{m.author.display_avatar.url}"><div>'
            f"<b>{html.escape(m.author.display_name)}</b> <span>{hora}</span>"
            f"<div>{texto}</div>{anexos}</div></div>"
        )

    pagina = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Transcript - {html.escape(canal.name)}</title>
<style>
body{{background:#313338;color:#dbdee1;font-family:Arial,sans-serif;padding:20px}}
.msg{{display:flex;gap:12px;margin:14px 0}}
.msg img{{width:40px;height:40px;border-radius:50%}}
.msg span{{color:#949ba4;font-size:12px;margin-left:6px}}
a{{color:#00a8fc}}
</style></head><body>
<h2>Transcript do canal #{html.escape(canal.name)}</h2><hr>
{''.join(blocos)}
</body></html>"""
    return pagina.encode("utf-8")


# --- Tickets ---
async def fechar_ticket(interaction: discord.Interaction):
    canal = interaction.channel
    topico = canal.topic or ""
    if not topico.startswith("ticket:"):
        await interaction.response.send_message("Isso não é um ticket.", ephemeral=True)
        return

    dono_id = int(topico.split(":")[1])
    if interaction.user.id != dono_id and not eh_staff(interaction.user):
        await interaction.response.send_message(
            "Só quem abriu o ticket ou a staff pode fechar.", ephemeral=True
        )
        return

    await interaction.response.send_message("🔒 Fechando o ticket e salvando o transcript...")

    try:
        conteudo = await gerar_transcript(canal)
        nome_arquivo = f"transcript-{canal.name}.html"

        logs = interaction.guild.get_channel(cfg["ids"]["logs"])
        if logs:
            await logs.send(
                f"📄 Transcript de **#{canal.name}** (fechado por {interaction.user.mention})",
                file=discord.File(io.BytesIO(conteudo), filename=nome_arquivo),
                allowed_mentions=discord.AllowedMentions.none(),
            )

        if cfg["ids"]["dm"]:
            dono = interaction.guild.get_member(dono_id)
            if dono:
                try:
                    await dono.send(
                        "📄 Aqui está o transcript do seu ticket:",
                        file=discord.File(io.BytesIO(conteudo), filename=nome_arquivo),
                    )
                except discord.Forbidden:
                    pass
    except Exception as e:
        print(f"[Transcript] erro: {e}")

    await asyncio.sleep(5)
    await canal.delete(reason=f"Ticket fechado por {interaction.user}")


class TicketView(discord.ui.LayoutView):
    """Mensagem do ticket. Sem 'dados' = versão mínima só para o botão persistir."""

    def __init__(self, dados: Optional[dict] = None):
        super().__init__(timeout=None)

        fechar = criar_botao("fechar", "ticket:fechar")
        fechar.callback = fechar_ticket

        if dados is None:
            self.add_item(discord.ui.Container(discord.ui.ActionRow(fechar)))
            return

        tipo = dados.get("tipo", "compra")
        usuario = dados["usuario"]
        cargo = dados["cargo"]
        agora = int(datetime.now(timezone.utc).timestamp())
        variaveis = {
            "usuario": usuario.mention,
            "cargo": cargo.mention if cargo else "atendente",
            "id": usuario.id,
            "item": dados.get("item", ""),
            "nick": dados.get("nick", ""),
            "preco": dados.get("preco", ""),
            "assunto": dados.get("assunto", ""),
            "data": f"<t:{agora}:f>",
        }
        chave_boas_vindas, chave_info = TIPOS_TICKET[tipo]["containers"]

        # primeiro a boas-vindas, com o botão de fechar
        boas_vindas = montar_container(chave_boas_vindas, variaveis)
        boas_vindas.add_item(discord.ui.Separator())
        boas_vindas.add_item(discord.ui.ActionRow(fechar))
        self.add_item(boas_vindas)

        # depois as informações do ticket
        self.add_item(montar_container(chave_info, variaveis))

        if tipo == "suporte":
            return

        # por fim a conta do Roblox (só em compra e venda)
        r = dados["roblox"]
        if r:
            variaveis.update(
                {
                    "nome": r["nome"],
                    "display": r["display"],
                    "id": r["id"],
                    "criado": f"<t:{r['criado']}:D> (<t:{r['criado']}:R>)",
                    "amigos": r["amigos"],
                    "link": r["link"],
                }
            )
            roblox = montar_container("roblox", variaveis, miniatura=r["avatar"])
            if r["banido"]:
                roblox.add_item(discord.ui.TextDisplay("⚠️ **Conta banida**"))
        else:
            roblox = discord.ui.Container(
                accent_colour=parse_cor(cfg["containers"]["roblox"]["cor"])
            )
            roblox.add_item(
                discord.ui.TextDisplay(formatar(cfg["roblox_erro"], {"nick": dados["nick"]}))
            )
        self.add_item(roblox)


async def abrir_ticket(interaction: discord.Interaction, tipo: str, dados: dict):
    """Cria o canal do ticket (tipo: compra, suporte ou venda) e manda as mensagens."""
    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = interaction.guild
    usuario = interaction.user

    categoria_id = cfg["ids"]["categoria"]
    if tipo != "compra" and cfg["ids"]["categoria_suporte"]:
        categoria_id = cfg["ids"]["categoria_suporte"]
    categoria = guild.get_channel(categoria_id)
    if not isinstance(categoria, discord.CategoryChannel):
        await interaction.followup.send(
            "⚠️ A categoria de tickets não está configurada. Avise a staff.", ephemeral=True
        )
        return

    topico = f"ticket:{usuario.id}:{tipo}"
    for canal in guild.text_channels:
        if canal.topic == topico:
            await interaction.followup.send(
                f"Você já tem um ticket desse tipo aberto: {canal.mention}", ephemeral=True
            )
            return

    cargo = guild.get_role(cfg["ids"]["cargo"])
    roblox = None
    if tipo in ("compra", "venda"):
        roblox = await buscar_roblox(dados["nick"])

    permissoes = dict(
        view_channel=True, send_messages=True, attach_files=True, read_message_history=True
    )
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        usuario: discord.PermissionOverwrite(**permissoes),
        guild.me: discord.PermissionOverwrite(
            **permissoes, manage_channels=True, embed_links=True
        ),
    }
    if cargo:
        overwrites[cargo] = discord.PermissionOverwrite(**permissoes, manage_messages=True)

    canal = await guild.create_text_channel(
        name=f"{TIPOS_TICKET[tipo]['prefixo']}-{usuario.name}"[:90],
        category=categoria,
        overwrites=overwrites,
        topic=topico,
        reason=f"Ticket ({tipo}) aberto por {usuario}",
    )

    # Mensagem simples só para garantir a notificação (marca usuário e cargo)
    mencoes = usuario.mention + (f" {cargo.mention}" if cargo else "")
    await canal.send(
        mencoes, allowed_mentions=discord.AllowedMentions(users=[usuario], roles=True)
    )

    dados.update({"tipo": tipo, "usuario": usuario, "cargo": cargo, "roblox": roblox})
    await canal.send(view=TicketView(dados), allowed_mentions=discord.AllowedMentions.none())
    await interaction.followup.send(f"✅ Ticket criado: {canal.mention}", ephemeral=True)


class TicketModal(discord.ui.Modal, title="Comprar MM2"):
    item = discord.ui.TextInput(
        label="Qual item você tem interesse?",
        placeholder="Ex: Harvester, Set Elderwood...",
        max_length=100,
    )
    nick = discord.ui.TextInput(
        label="Seu Nick no Roblox",
        placeholder="Ex: NickDoRoblox123",
        min_length=3,
        max_length=20,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await abrir_ticket(
            interaction,
            "compra",
            {"item": self.item.value.strip(), "nick": self.nick.value.strip()},
        )


# --- Carrinho: escolher os itens e conferir o resumo do pedido ---
CARRINHOS_ARQUIVO = Path("carrinhos.json")
COR_CARRINHO = "#8B5CF6"
TEXTO_DROPDOWN = "Escolher"  # texto antes do nome da seção nos menus de escolher itens


def carregar_carrinhos() -> dict:
    if CARRINHOS_ARQUIVO.exists():
        return json.loads(CARRINHOS_ARQUIVO.read_text(encoding="utf-8"))
    return {}


def salvar_carrinhos(dados: dict) -> None:
    CARRINHOS_ARQUIVO.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ler_carrinho(canal_id) -> dict:
    return carregar_carrinhos().get(str(canal_id), {"itens": {}})


def gravar_carrinho(canal_id, carrinho: dict) -> None:
    dados = carregar_carrinhos()
    dados[str(canal_id)] = carrinho
    salvar_carrinhos(dados)


def preco_para_float(txt) -> float:
    limpo = str(txt).replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def moeda(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def separar_emoji(nome: str):
    """'<:123:456> Bat' vira ('<:123:456>', 'Bat')."""
    m = re.match(r"^\s*(<a?:\w+:\d+>)\s*(.*)$", nome)
    if m:
        return m.group(1), (m.group(2) or nome).strip()
    return "", nome.strip()


def chave_item(cat: str, item: dict) -> str:
    return f"{cat}|{item['nome']}"[:100]


def achar_item(chave: str) -> Optional[dict]:
    cat = chave.split("|")[0]
    for item in carregar_estoque().get(cat, []):
        if chave_item(cat, item) == chave:
            return item
    return None


def opcao_item(chave: str, item: dict, descricao: str) -> discord.SelectOption:
    emoji_txt, nome = separar_emoji(item["nome"])
    return discord.SelectOption(
        label=nome[:100],
        value=chave,
        description=descricao[:100],
        emoji=discord.PartialEmoji.from_str(emoji_txt) if emoji_txt else None,
    )


# Etapa 1: escolher itens
class CarrinhoEscolherView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        c = discord.ui.Container(accent_colour=parse_cor(COR_CARRINHO))
        c.add_item(
            discord.ui.TextDisplay(
                "## 🛒 ESCOLHA SEUS ITENS\n"
                "Selecione abaixo o que você quer comprar. "
                "Depois você revisa o pedido antes de finalizar. ♡"
            )
        )
        estoque = carregar_estoque()
        for cat, titulo in categorias():
            opcoes = [
                opcao_item(chave_item(cat, i), i, f"R$ {i['preco']} • {i['qtd']} un.")
                for i in sorted(estoque[cat], key=lambda i: preco_para_float(i["preco"]), reverse=True)
                if i["qtd"] > 0
            ][:25]
            if not opcoes:
                continue
            # emoji personalizado (<:id:id>) não aparece no placeholder, então tiramos o código
            titulo_limpo = re.sub(r"<a?:\w+:\d+>", "", titulo).strip()
            menu = discord.ui.Select(
                custom_id=f"carrinho:escolher:{cat}",
                placeholder=f"{TEXTO_DROPDOWN}: {titulo_limpo}"[:150],
                min_values=1,
                max_values=len(opcoes),
                options=opcoes,
            )
            menu.callback = escolher_itens
            c.add_item(discord.ui.Separator())
            c.add_item(discord.ui.ActionRow(menu))

        ver = discord.ui.Button(
            label="Ver meu carrinho", emoji="🛒",
            style=discord.ButtonStyle.secondary, custom_id="carrinho:ver",
        )
        ver.callback = ver_carrinho
        encerrar = discord.ui.Button(
            label="Encerrar Carrinho", emoji="✖️",
            style=discord.ButtonStyle.danger, custom_id="carrinho:encerrar",
        )
        encerrar.callback = fechar_ticket
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.ActionRow(ver, encerrar))
        self.add_item(c)


async def escolher_itens(interaction: discord.Interaction):
    carrinho = ler_carrinho(interaction.channel_id)
    for chave in interaction.data.get("values", []):
        item = achar_item(chave)
        if item and item["qtd"] > 0:
            carrinho["itens"].setdefault(chave, 1)
    gravar_carrinho(interaction.channel_id, carrinho)
    await interaction.response.edit_message(view=CarrinhoResumoView(interaction.channel_id))


async def ver_carrinho(interaction: discord.Interaction):
    if not ler_carrinho(interaction.channel_id)["itens"]:
        await interaction.response.send_message(
            "Seu carrinho está vazio. Escolha algum item primeiro.", ephemeral=True
        )
        return
    await interaction.response.edit_message(view=CarrinhoResumoView(interaction.channel_id))


# Etapa 2: resumo do pedido
class CarrinhoResumoView(discord.ui.LayoutView):
    def __init__(self, canal_id: Optional[int] = None):
        super().__init__(timeout=None)
        itens = []
        if canal_id:
            for chave, qtd in ler_carrinho(canal_id)["itens"].items():
                item = achar_item(chave)
                if item:
                    itens.append((chave, item, qtd))

        linhas, total, unidades = [], 0.0, 0
        for chave, item, qtd in itens:
            emoji_txt, nome = separar_emoji(item["nome"])
            subtotal = preco_para_float(item["preco"]) * qtd
            total += subtotal
            unidades += qtd
            prefixo = f"( {emoji_txt} ) " if emoji_txt else ""
            linhas.append(f"- {prefixo}`{qtd}x {nome} - {moeda(subtotal)}`")

        c = discord.ui.Container(accent_colour=parse_cor(COR_CARRINHO))
        c.add_item(discord.ui.TextDisplay("## 🛒 RESUMO DO PEDIDO"))
        c.add_item(
            discord.ui.TextDisplay(
                "**Seus itens selecionados**\n" + ("\n".join(linhas) or "(vazio)")
            )
        )
        c.add_item(discord.ui.Separator())
        c.add_item(
            discord.ui.TextDisplay(
                f"💵 **Valor Total**\n`{moeda(total)}`\n"
                f"🛒 **Unidades**\n`{unidades} produto(s)`"
            )
        )

        # menu para ajustar a quantidade de cada item
        opcoes = [
            opcao_item(chave, item, f"Quantidade atual: {qtd} (máx {item['qtd']})")
            for chave, item, qtd in itens
        ][:25] or [discord.SelectOption(label="(carrinho vazio)", value="vazio")]
        menu = discord.ui.Select(
            custom_id="carrinho:quantidade",
            placeholder="Ajustar quantidade dos itens",
            options=opcoes,
        )
        menu.callback = ajustar_quantidade
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.ActionRow(menu))

        finalizar = discord.ui.Button(
            label="Finalizar Pedido", emoji="✅",
            style=discord.ButtonStyle.success, custom_id="carrinho:finalizar",
        )
        finalizar.callback = finalizar_pedido
        mais = discord.ui.Button(
            label="Escolher Mais Itens", emoji="🛍️",
            style=discord.ButtonStyle.secondary, custom_id="carrinho:mais",
        )
        mais.callback = escolher_mais
        limpar = discord.ui.Button(
            label="Limpar Carrinho", emoji="🗑️",
            style=discord.ButtonStyle.danger, custom_id="carrinho:limpar",
        )
        limpar.callback = limpar_carrinho
        encerrar = discord.ui.Button(
            label="Encerrar Carrinho", emoji="✖️",
            style=discord.ButtonStyle.danger, custom_id="carrinho:encerrar2",
        )
        encerrar.callback = fechar_ticket
        c.add_item(discord.ui.ActionRow(finalizar, mais, limpar))
        c.add_item(discord.ui.ActionRow(encerrar))
        self.add_item(c)


class QuantidadeModal(discord.ui.Modal):
    def __init__(self, chave: str, atual: int, maximo: int):
        super().__init__(title="Quantidade do item")
        self.chave = chave
        self.maximo = maximo
        self.campo = discord.ui.TextInput(
            label=f"Quantas unidades? (máx {maximo}, 0 remove)",
            default=str(atual),
            min_length=1,
            max_length=4,
        )
        self.add_item(self.campo)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(self.campo.value.strip())
        except ValueError:
            await interaction.response.send_message("Digite só números.", ephemeral=True)
            return
        if n < 0 or n > self.maximo:
            await interaction.response.send_message(
                f"Quantidade inválida. Temos no máximo {self.maximo} em estoque.",
                ephemeral=True,
            )
            return

        carrinho = ler_carrinho(interaction.channel_id)
        if n == 0:
            carrinho["itens"].pop(self.chave, None)
        else:
            carrinho["itens"][self.chave] = n
        gravar_carrinho(interaction.channel_id, carrinho)

        if carrinho["itens"]:
            view = CarrinhoResumoView(interaction.channel_id)
        else:
            view = CarrinhoEscolherView()
        await interaction.response.edit_message(view=view)


async def ajustar_quantidade(interaction: discord.Interaction):
    valores = interaction.data.get("values", [])
    chave = valores[0] if valores else ""
    item = achar_item(chave)
    if not item:
        await interaction.response.send_message(
            "Esse item não está mais disponível.", ephemeral=True
        )
        return
    atual = ler_carrinho(interaction.channel_id)["itens"].get(chave, 1)
    await interaction.response.send_modal(QuantidadeModal(chave, atual, item["qtd"]))


async def escolher_mais(interaction: discord.Interaction):
    await interaction.response.edit_message(view=CarrinhoEscolherView())


async def limpar_carrinho(interaction: discord.Interaction):
    gravar_carrinho(interaction.channel_id, {"itens": {}})
    await interaction.response.edit_message(view=CarrinhoEscolherView())


async def finalizar_pedido(interaction: discord.Interaction):
    # Confere o estoque de novo antes de seguir
    problemas = []
    for chave, qtd in ler_carrinho(interaction.channel_id)["itens"].items():
        item = achar_item(chave)
        if not item or item["qtd"] < qtd:
            problemas.append(separar_emoji(item["nome"])[1] if item else chave.split("|")[-1])
    if problemas:
        await interaction.response.send_message(
            "⚠️ Estoque mudou para: " + ", ".join(problemas) + ". Ajuste a quantidade.",
            ephemeral=True,
        )
        return
    atualizar_carrinho(interaction.channel_id, pedido=montar_pedido(interaction.channel_id))
    await interaction.response.edit_message(view=CarrinhoPagamentoView(interaction.channel_id))


async def abrir_carrinho(interaction: discord.Interaction):
    """Cria o canal privado do carrinho e manda o menu de itens."""
    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = interaction.guild
    usuario = interaction.user

    categoria = guild.get_channel(cfg["ids"]["categoria"])
    if not isinstance(categoria, discord.CategoryChannel):
        await interaction.followup.send(
            "⚠️ A categoria de tickets não está configurada. Avise a staff.", ephemeral=True
        )
        return

    topico = f"ticket:{usuario.id}:compra"  # mesmo formato do ticket, o fechar/transcript continua igual
    for canal in guild.text_channels:
        if canal.topic == topico:
            await interaction.followup.send(
                f"Você já tem um carrinho aberto: {canal.mention}", ephemeral=True
            )
            return

    cargo = guild.get_role(cfg["ids"]["cargo"])
    permissoes = dict(
        view_channel=True, send_messages=True, attach_files=True, read_message_history=True
    )
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        usuario: discord.PermissionOverwrite(**permissoes),
        guild.me: discord.PermissionOverwrite(
            **permissoes, manage_channels=True, embed_links=True
        ),
    }
    if cargo:
        overwrites[cargo] = discord.PermissionOverwrite(**permissoes, manage_messages=True)

    canal = await guild.create_text_channel(
        name=f"carrinho-{usuario.name}"[:90],
        category=categoria,
        overwrites=overwrites,
        topic=topico,
        reason=f"Carrinho aberto por {usuario}",
    )
    gravar_carrinho(canal.id, {"dono": usuario.id, "itens": {}})

    await canal.send(
        usuario.mention, allowed_mentions=discord.AllowedMentions(users=[usuario])
    )
    await canal.send(view=CarrinhoEscolherView(), allowed_mentions=discord.AllowedMentions.none())
    await interaction.followup.send(f"✅ Carrinho criado: {canal.mention}", ephemeral=True)


# --- Carrinho: Pix, conta do Roblox, entrega e comprovante ---
LOGO_ARQUIVO = Path("logo.png")
_cache_loja = {"dados": None, "quando": 0.0}


def atualizar_carrinho(canal_id, **campos) -> dict:
    carrinho = ler_carrinho(canal_id)
    carrinho.update(campos)
    gravar_carrinho(canal_id, carrinho)
    return carrinho


def montar_pedido(canal_id) -> list:
    """Foto do carrinho: nome, quantidade e preço de cada item no momento do pedido."""
    pedido = []
    for chave, qtd in ler_carrinho(canal_id)["itens"].items():
        item = achar_item(chave)
        if item:
            pedido.append({"nome": item["nome"], "qtd": qtd, "preco": item["preco"]})
    return pedido


def pedido_atual(canal_id) -> list:
    return ler_carrinho(canal_id).get("pedido") or montar_pedido(canal_id)


def texto_pedido(pedido: list):
    """Devolve (linhas em texto, valor total, unidades) no estilo - ( emoji ) `1x Nome - R$ 0,00`."""
    linhas, total, unidades = [], 0.0, 0
    for p in pedido:
        emoji_txt, nome = separar_emoji(p["nome"])
        subtotal = preco_para_float(p["preco"]) * p["qtd"]
        total += subtotal
        unidades += p["qtd"]
        prefixo = f"( {emoji_txt} ) " if emoji_txt else ""
        linhas.append(f"- {prefixo}`{p['qtd']}x {nome} - {moeda(subtotal)}`")
    return "\n".join(linhas) or "(vazio)", total, unidades


async def so_dono(interaction: discord.Interaction) -> bool:
    dono = ler_carrinho(interaction.channel_id).get("dono")
    if dono and interaction.user.id != dono and not eh_staff(interaction.user):
        await interaction.response.send_message(
            "Só quem abriu o carrinho pode usar isso.", ephemeral=True
        )
        return False
    return True


async def renomear_canal(canal, nome: str):
    """Renomeia sem travar o bot se o Discord limitar (só 2 trocas a cada 10 min)."""
    try:
        await asyncio.wait_for(canal.edit(name=nome[:90]), timeout=4)
    except Exception as e:
        print(f"[Canal] não consegui renomear: {e}")


async def dados_loja():
    """Perfil do Roblox da loja (quem faz as trocas). Guarda 10 min para não buscar toda hora."""
    agora = time.time()
    if _cache_loja["dados"] and agora - _cache_loja["quando"] < 600:
        return _cache_loja["dados"]
    dados = await buscar_roblox(cfg["loja"]["roblox_loja"])
    if dados:
        _cache_loja["dados"] = dados
        _cache_loja["quando"] = agora
    return dados


# Pix (código copia e cola + QR code)
def sem_acento(txt: str) -> str:
    return unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")


def _tlv(id_: str, valor: str) -> str:
    return f"{id_}{len(valor):02d}{valor}"


def crc16(texto: str) -> str:
    crc = 0xFFFF
    for byte in texto.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def limpar_chave_pix(chave: str) -> str:
    chave = chave.strip().replace(" ", "")
    if "@" in chave or len(chave) == 36:  # e-mail ou chave aleatória
        return chave
    if chave.startswith("+"):  # telefone: +5511999999999
        return "+" + re.sub(r"\D", "", chave)
    return re.sub(r"\D", "", chave)  # CPF ou CNPJ


def gerar_pix_payload(chave: str, nome: str, cidade: str, valor: float) -> str:
    conta = _tlv("00", "br.gov.bcb.pix") + _tlv("01", limpar_chave_pix(chave))
    corpo = (
        _tlv("00", "01")
        + _tlv("01", "12")
        + _tlv("26", conta)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("54", f"{valor:.2f}")
        + _tlv("58", "BR")
        + _tlv("59", sem_acento(nome).upper()[:25])
        + _tlv("60", sem_acento(cidade).upper()[:15])
        + _tlv("62", _tlv("05", "***"))
        + "6304"
    )
    return corpo + crc16(corpo)


def gerar_qr(payload: str) -> bytes:
    import qrcode
    from PIL import Image

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    if LOGO_ARQUIVO.exists():
        logo = Image.open(LOGO_ARQUIVO).convert("RGBA")
        logo.thumbnail((img.width // 5, img.height // 5))
        img.alpha_composite(logo, ((img.width - logo.width) // 2, (img.height - logo.height) // 2))
    saida = io.BytesIO()
    img.convert("RGB").save(saida, "PNG")
    return saida.getvalue()


def pix_configurado() -> bool:
    return bool(cfg["loja"]["pix_chave"] and cfg["loja"]["pix_nome"])


# Marca d'água do comprovante de entrega
def marcar_imagem(dados: bytes) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    base = Image.open(io.BytesIO(dados)).convert("RGBA")
    if LOGO_ARQUIVO.exists():
        logo = Image.open(LOGO_ARQUIVO).convert("RGBA")
        largura = max(80, int(base.width * 0.35))
        altura = max(1, int(logo.height * largura / logo.width))
        logo = logo.resize((largura, altura), Image.Resampling.LANCZOS)
        logo.putalpha(logo.getchannel("A").point(lambda v: int(v * 0.45)))  # 45% visível
        base.alpha_composite(logo, ((base.width - largura) // 2, (base.height - altura) // 2))
    else:  # sem logo.png: usa o nome da loja como texto
        camada = Image.new("RGBA", base.size, (0, 0, 0, 0))
        desenho = ImageDraw.Draw(camada)
        texto = cfg["loja"]["nome"].upper()
        try:
            fonte = ImageFont.load_default(size=max(24, base.width // 10))
        except TypeError:
            fonte = ImageFont.load_default()
        caixa = desenho.textbbox((0, 0), texto, font=fonte)
        x = (base.width - (caixa[2] - caixa[0])) // 2
        y = (base.height - (caixa[3] - caixa[1])) // 2
        desenho.text((x, y), texto, font=fonte, fill=(255, 255, 255, 110))
        base = Image.alpha_composite(base, camada)
    saida = io.BytesIO()
    base.convert("RGB").save(saida, "PNG")
    return saida.getvalue()


# Etapa 3a: escolher a forma de pagamento
class CarrinhoPagamentoView(discord.ui.LayoutView):
    def __init__(self, canal_id: Optional[int] = None):
        super().__init__(timeout=None)
        linhas, total, unidades = texto_pedido(pedido_atual(canal_id) if canal_id else [])
        c = discord.ui.Container(accent_colour=parse_cor(COR_CARRINHO))
        c.add_item(discord.ui.TextDisplay("## 🛒 RESUMO DO PEDIDO"))
        c.add_item(discord.ui.TextDisplay(f"**Seus itens selecionados**\n{linhas}"))
        c.add_item(discord.ui.Separator())
        c.add_item(
            discord.ui.TextDisplay(
                f"💵 **Valor Total**\n`{moeda(total)}`\n🛒 **Unidades**\n`{unidades} produto(s)`"
            )
        )
        c.add_item(discord.ui.Separator())
        c.add_item(
            discord.ui.TextDisplay(
                "## ✦ QUASE TUDO PRONTO!\n"
                "✦ Confira os itens selecionados e o valor total do seu pedido.\n\n"
                "**Próxima etapa**\n"
                "Se estiver tudo correto, escolha abaixo sua forma de pagamento para continuar.\n\n"
                f"♡ Obrigado por escolher a **{cfg['loja']['nome']}**!"
            )
        )
        menu = discord.ui.Select(
            custom_id="carrinho:pagamento",
            placeholder="Escolha a forma de pagamento",
            options=[discord.SelectOption(label="Pix", value="pix", emoji="💠")],
        )
        menu.callback = escolher_pagamento
        voltar = discord.ui.Button(
            label="Voltar", emoji="⬅️", style=discord.ButtonStyle.primary,
            custom_id="carrinho:voltar_resumo",
        )
        voltar.callback = voltar_resumo
        encerrar = discord.ui.Button(
            label="Encerrar Carrinho", emoji="✖️", style=discord.ButtonStyle.danger,
            custom_id="carrinho:encerrar3",
        )
        encerrar.callback = fechar_ticket
        c.add_item(discord.ui.ActionRow(menu))
        c.add_item(discord.ui.ActionRow(voltar, encerrar))
        self.add_item(c)


async def voltar_resumo(interaction: discord.Interaction):
    await interaction.response.edit_message(view=CarrinhoResumoView(interaction.channel_id))


async def escolher_pagamento(interaction: discord.Interaction):
    if not await so_dono(interaction):
        return
    atual = ler_carrinho(interaction.channel_id).get("roblox_nick", "")
    await interaction.response.send_modal(RobloxNickModal(atual))


# Etapa 3b: nick do Roblox e confirmação da conta
class RobloxNickModal(discord.ui.Modal):
    def __init__(self, atual: str = ""):
        super().__init__(title="Usuário no Roblox")
        self.campo = discord.ui.TextInput(
            label="Seu usuário no Roblox",
            placeholder="Ex: NickDoRoblox123",
            default=atual or None,
            min_length=3,
            max_length=20,
        )
        self.add_item(self.campo)

    async def on_submit(self, interaction: discord.Interaction):
        nick = self.campo.value.strip()
        await interaction.response.defer()  # a busca no Roblox pode passar de 3 segundos
        dados = await buscar_roblox(nick)
        atualizar_carrinho(interaction.channel_id, roblox_nick=nick, roblox=dados)
        await interaction.edit_original_response(view=CarrinhoPerfilView(interaction.channel_id))


class CarrinhoPerfilView(discord.ui.LayoutView):
    def __init__(self, canal_id: Optional[int] = None):
        super().__init__(timeout=None)
        carrinho = ler_carrinho(canal_id) if canal_id else {}
        r = carrinho.get("roblox")
        loja = cfg["loja"]["nome"]

        c = discord.ui.Container(accent_colour=parse_cor(COR_CARRINHO))
        c.add_item(discord.ui.TextDisplay(f"## {loja}"))
        if r:
            texto = (
                "## ✦ CONFIRME SUA CONTA\n\n"
                f"✦ Encontramos o perfil **{r['nome']}**. "
                "Confira os dados exibidos abaixo antes de continuar com seu pedido.\n\n"
                f"👤 **Nome de Exibição**\n`{r['display']}`\n"
                f"🪪 **Nome da Conta**\n`{r['nome']}`\n\n"
                "**Tudo certinho?**\n"
                "Confirme se este é o perfil que receberá seus itens. Caso encontre alguma "
                "informação incorreta, selecione **Alterar Perfil** antes de prosseguir. ♡"
            )
            if r.get("banido"):
                texto += "\n\n⚠️ **Conta banida**"
            if r.get("avatar"):
                c.add_item(
                    discord.ui.Section(
                        discord.ui.TextDisplay(texto), accessory=discord.ui.Thumbnail(r["avatar"])
                    )
                )
            else:
                c.add_item(discord.ui.TextDisplay(texto))
        else:
            nick = carrinho.get("roblox_nick", "")
            c.add_item(
                discord.ui.TextDisplay(
                    "## ✦ CONFIRME SUA CONTA\n\n"
                    f"⚠️ Não encontrei o usuário `{nick}` no Roblox. "
                    "Clique em **Alterar Perfil** e digite o nick de novo."
                )
            )

        confirmar = discord.ui.Button(
            label="Confirmar Perfil", emoji="✅", style=discord.ButtonStyle.success,
            custom_id="carrinho:perfil_ok", disabled=not r,
        )
        confirmar.callback = perfil_ok
        alterar = discord.ui.Button(
            label="Alterar Perfil", emoji="✏️", style=discord.ButtonStyle.secondary,
            custom_id="carrinho:perfil_alterar",
        )
        alterar.callback = perfil_alterar
        voltar = discord.ui.Button(
            label="Voltar para o Carrinho de Compras", emoji="⬅️",
            style=discord.ButtonStyle.primary, custom_id="carrinho:perfil_voltar",
        )
        voltar.callback = voltar_resumo
        c.add_item(discord.ui.ActionRow(confirmar, alterar))
        c.add_item(discord.ui.ActionRow(voltar))
        self.add_item(c)


async def perfil_alterar(interaction: discord.Interaction):
    if not await so_dono(interaction):
        return
    atual = ler_carrinho(interaction.channel_id).get("roblox_nick", "")
    await interaction.response.send_modal(RobloxNickModal(atual))


# Etapa 4: pagamento Pix
class CarrinhoPixView(discord.ui.LayoutView):
    def __init__(self, canal_id: Optional[int] = None):
        super().__init__(timeout=None)
        carrinho = ler_carrinho(canal_id) if canal_id else {}
        linhas, total, _ = texto_pedido(pedido_atual(canal_id) if canal_id else [])
        r = carrinho.get("roblox") or {}
        usuario = (
            f"[{r['display']}]({r['link']}) (`@{r['nome']}`)" if r else carrinho.get("roblox_nick", "-")
        )

        c = discord.ui.Container(accent_colour=parse_cor(COR_CARRINHO))
        c.add_item(discord.ui.TextDisplay("## 🛒 PAGAMENTO PIX"))
        c.add_item(discord.ui.TextDisplay(f"**Seus itens selecionados**\n{linhas}"))
        c.add_item(
            discord.ui.TextDisplay(
                f"👤 **Usuário no Roblox**\n{usuario}\n💵 **Valor Total**\n`{moeda(total)}`"
            )
        )
        c.add_item(discord.ui.Separator())
        c.add_item(
            discord.ui.TextDisplay(
                "## ✦ REALIZE SEU PAGAMENTO\n"
                "✦ Escaneie o QR Code abaixo ou utilize a opção **Copia e Cola** para efetuar o Pix.\n\n"
                "**Confirmação do pedido**\n"
                "Após o pagamento, envie o comprovante (**print ou PDF**) neste atendimento "
                "e aguarde a verificação de nossa equipe.\n\n"
                "♡ Seu pedido será liberado após a confirmação do pagamento."
            )
        )
        c.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://pix.png")))

        copia = discord.ui.Button(
            label="Copia e Cola", emoji="📋", style=discord.ButtonStyle.primary,
            custom_id="carrinho:copiacola",
        )
        copia.callback = pedir_copia_e_cola
        confirmar = discord.ui.Button(
            label="Confirmar Pagamento (Staff)", emoji="✅", style=discord.ButtonStyle.success,
            custom_id="carrinho:confirmar_pagamento",
        )
        confirmar.callback = confirmar_pagamento
        encerrar = discord.ui.Button(
            label="Encerrar Carrinho", emoji="✖️", style=discord.ButtonStyle.danger,
            custom_id="carrinho:encerrar4",
        )
        encerrar.callback = fechar_ticket
        c.add_item(discord.ui.ActionRow(copia))
        c.add_item(discord.ui.ActionRow(confirmar, encerrar))
        self.add_item(c)


class PerfilConfirmadoView(discord.ui.LayoutView):
    """Troca a tela de confirmar conta por um aviso curto (o Pix vem na mensagem de baixo)."""

    def __init__(self, canal_id: int):
        super().__init__(timeout=None)
        r = ler_carrinho(canal_id).get("roblox") or {}
        c = discord.ui.Container(accent_colour=parse_cor("#57F287"))
        c.add_item(
            discord.ui.TextDisplay(
                "## ✅ PERFIL CONFIRMADO\n"
                f"Conta: **{r.get('display', '-')}** (`@{r.get('nome', '-')}`)\n\n"
                "↓ O pagamento Pix está logo abaixo."
            )
        )
        self.add_item(c)


class PagamentoConfirmadoView(discord.ui.LayoutView):
    """Substitui a mensagem do Pix depois que a staff confirma (sem botões)."""

    def __init__(self, canal_id: int, staff_id: int):
        super().__init__(timeout=None)
        linhas, total, unidades = texto_pedido(pedido_atual(canal_id))
        c = discord.ui.Container(accent_colour=parse_cor("#57F287"))
        c.add_item(discord.ui.TextDisplay("## ✅ PAGAMENTO CONFIRMADO"))
        c.add_item(discord.ui.TextDisplay(f"**Itens do pedido**\n{linhas}"))
        c.add_item(
            discord.ui.TextDisplay(
                f"💵 **Valor Total**\n`{moeda(total)}`\n🛒 **Unidades**\n`{unidades} produto(s)`\n\n"
                f"Confirmado por <@{staff_id}>"
            )
        )
        self.add_item(c)


async def perfil_ok(interaction: discord.Interaction):
    if not await so_dono(interaction):
        return
    carrinho = ler_carrinho(interaction.channel_id)
    if not carrinho.get("roblox"):
        await interaction.response.send_message(
            "Não achei esse perfil. Clique em Alterar Perfil.", ephemeral=True
        )
        return
    if not pix_configurado():
        await interaction.response.send_message(
            "⚠️ O Pix da loja ainda não foi configurado. Avise a staff.", ephemeral=True
        )
        return

    await interaction.response.defer()
    pedido = pedido_atual(interaction.channel_id)
    _, total, _ = texto_pedido(pedido)
    loja = cfg["loja"]
    payload = gerar_pix_payload(loja["pix_chave"], loja["pix_nome"], loja["pix_cidade"], total)
    try:
        qr = await asyncio.to_thread(gerar_qr, payload)
    except ImportError:
        await interaction.followup.send(
            "⚠️ Falta instalar a biblioteca do QR Code (`pip install qrcode[pil]`). Avise a staff.",
            ephemeral=True,
        )
        return

    atualizar_carrinho(
        interaction.channel_id, pedido=pedido, total=total, pix_codigo=payload,
        status="aguardando_pagamento",
    )
    await interaction.channel.send(
        view=CarrinhoPixView(interaction.channel_id),
        file=discord.File(io.BytesIO(qr), filename="pix.png"),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    await interaction.edit_original_response(view=PerfilConfirmadoView(interaction.channel_id))

    cargo = interaction.guild.get_role(cfg["ids"]["cargo"])
    if cargo:
        await interaction.channel.send(
            f"🔔 {cargo.mention} novo pedido de {interaction.user.mention} "
            f"aguardando pagamento (**{moeda(total)}**).",
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
    await renomear_canal(interaction.channel, f"🟡・pendente・{carrinho['roblox']['nome']}")


async def pedir_copia_e_cola(interaction: discord.Interaction):
    codigo = ler_carrinho(interaction.channel_id).get("pix_codigo")
    if not codigo:
        await interaction.response.send_message("Código Pix não encontrado.", ephemeral=True)
        return
    await interaction.response.send_message(
        "📋 **Pix Copia e Cola**\nCopie o código abaixo e cole no app do seu banco:\n"
        f"```{codigo}```",
        ephemeral=True,
    )


def descontar_estoque(pedido: list) -> list:
    """Tira do estoque o que foi vendido. Devolve os nomes que não tinham quantidade suficiente."""
    dados = carregar_estoque()
    faltaram = []
    for p in pedido:
        for cat in CATEGORIAS_ESTOQUE:
            for item in dados[cat]:
                if item["nome"] == p["nome"]:
                    if item["qtd"] < p["qtd"]:
                        faltaram.append(separar_emoji(p["nome"])[1])
                    item["qtd"] = max(0, item["qtd"] - p["qtd"])
    salvar_estoque(dados)
    return faltaram


async def confirmar_pagamento(interaction: discord.Interaction):
    if not eh_staff(interaction.user):
        await interaction.response.send_message(
            "Só a staff pode confirmar o pagamento.", ephemeral=True
        )
        return
    carrinho = ler_carrinho(interaction.channel_id)
    if carrinho.get("status") != "aguardando_pagamento":
        await interaction.response.send_message("Esse pagamento já foi confirmado.", ephemeral=True)
        return

    await interaction.response.defer()
    faltaram = descontar_estoque(carrinho.get("pedido", []))
    atualizar_carrinho(interaction.channel_id, status="pago", confirmado_por=interaction.user.id)
    await interaction.edit_original_response(
        view=PagamentoConfirmadoView(interaction.channel_id, interaction.user.id), attachments=[]
    )

    dono = interaction.guild.get_member(carrinho.get("dono", 0))
    loja = await dados_loja()
    await interaction.channel.send(
        f"✅ {dono.mention if dono else ''} seu pagamento foi confirmado!",
        allowed_mentions=discord.AllowedMentions(users=True),
    )
    await interaction.channel.send(
        view=CarrinhoEntregaView(interaction.channel_id, loja),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    if faltaram:
        await interaction.followup.send(
            "⚠️ O estoque não tinha quantidade suficiente de: " + ", ".join(faltaram),
            ephemeral=True,
        )
    nome = (carrinho.get("roblox") or {}).get("nome", interaction.channel.name)
    await renomear_canal(interaction.channel, f"🟢・pago・{nome}")


# Etapa 5: entrega e comprovante
class CarrinhoEntregaView(discord.ui.LayoutView):
    def __init__(self, canal_id: Optional[int] = None, loja: Optional[dict] = None):
        super().__init__(timeout=None)
        nick_loja = (loja or {}).get("nome") or cfg["loja"]["roblox_loja"]
        link_servidor = cfg["loja"]["link_servidor"]

        texto = (
            "## ✦ ENTREGA DOS ITENS\n"
            "♡ Pagamento confirmado! Agora é só receber seus itens:\n\n"
            "**1.** Entre no servidor pelo link abaixo.\n"
            f"**2.** Aguarde o usuário **{nick_loja}** mandar o pedido de troca para você.\n"
            "**3.** Aceite a troca e confira os itens.\n\n"
            "Quando já estiver dentro do servidor, clique em **Estou pronto para receber**."
        )
        if link_servidor:
            texto += f"\n\n🔗 **Servidor:** {link_servidor}"
        else:
            texto += "\n\n⚠️ O link do servidor ainda não foi configurado, aguarde o atendente."

        c = discord.ui.Container(accent_colour=parse_cor("#57F287"))
        if loja and loja.get("avatar"):
            c.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(texto), accessory=discord.ui.Thumbnail(loja["avatar"])
                )
            )
        else:
            c.add_item(discord.ui.TextDisplay(texto))

        links = []
        if link_servidor:
            links.append(
                discord.ui.Button(
                    label="Entrar no servidor", emoji="🎮",
                    style=discord.ButtonStyle.link, url=link_servidor,
                )
            )
        links.append(
            discord.ui.Button(
                label="Adicionar amigo no Roblox", emoji="➕", style=discord.ButtonStyle.link,
                url=(loja or {}).get("link") or "https://www.roblox.com",
            )
        )
        pronto = discord.ui.Button(
            label="Estou pronto para receber", emoji="🙋", style=discord.ButtonStyle.success,
            custom_id="carrinho:pronto",
        )
        pronto.callback = estou_pronto
        registrar = discord.ui.Button(
            label="Registrar entrega (Staff)", emoji="📸", style=discord.ButtonStyle.primary,
            custom_id="carrinho:registrar_entrega",
        )
        registrar.callback = registrar_entrega
        encerrar = discord.ui.Button(
            label="Fechar ticket", emoji="🔒", style=discord.ButtonStyle.danger,
            custom_id="carrinho:encerrar5",
        )
        encerrar.callback = fechar_ticket
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.ActionRow(*links))
        c.add_item(discord.ui.ActionRow(pronto))
        c.add_item(discord.ui.ActionRow(registrar, encerrar))
        self.add_item(c)


async def estou_pronto(interaction: discord.Interaction):
    carrinho = ler_carrinho(interaction.channel_id)
    if interaction.user.id != carrinho.get("dono"):
        await interaction.response.send_message(
            "Só quem fez o pedido pode usar esse botão.", ephemeral=True
        )
        return
    agora = time.time()
    if agora - carrinho.get("pronto_em", 0) < 120:
        await interaction.response.send_message(
            "Já avisei o atendente, aguarde um instante. ♡", ephemeral=True
        )
        return
    atualizar_carrinho(interaction.channel_id, pronto_em=agora)

    atendente = interaction.guild.get_member(carrinho.get("confirmado_por", 0))
    cargo = interaction.guild.get_role(cfg["ids"]["cargo"])
    marca = atendente.mention if atendente else (cargo.mention if cargo else "atendente")
    await interaction.response.send_message(
        "✅ Avisei o atendente! Aguarde o pedido de troca no Roblox.", ephemeral=True
    )
    await interaction.channel.send(
        f"🔔 {marca}, {interaction.user.mention} está **pronto para receber** os itens!",
        allowed_mentions=discord.AllowedMentions(users=True, roles=True),
    )


def container_prova(numero: int, cliente: str, staff_id: int, pedido: list, total: float, ts: int):
    linhas, _, _ = texto_pedido(pedido)
    c = discord.ui.Container(accent_colour=parse_cor("#3B82F6"))
    c.add_item(discord.ui.TextDisplay(f"## PROOF {numero}"))
    c.add_item(
        discord.ui.TextDisplay(
            f"✅ **Entrega concluída**\n**Cliente:** {cliente}\n**Entregue por:** <@{staff_id}>"
        )
    )
    c.add_item(discord.ui.TextDisplay(f"📦 **Itens entregues**\n{linhas}"))
    c.add_item(discord.ui.TextDisplay(f"🏷️ **Valor total**\n`{moeda(total)}`"))
    c.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem("attachment://entrega.png")))
    c.add_item(discord.ui.TextDisplay(f"-# Registro de entrega | <t:{ts}:f>"))
    view = discord.ui.LayoutView()
    view.add_item(c)
    return view


async def registrar_entrega(interaction: discord.Interaction):
    if not eh_staff(interaction.user):
        await interaction.response.send_message(
            "Só a staff pode registrar a entrega.", ephemeral=True
        )
        return
    carrinho = ler_carrinho(interaction.channel_id)
    if carrinho.get("status") != "pago":
        texto = (
            "Essa entrega já foi registrada."
            if carrinho.get("status") == "entregue"
            else "O pagamento ainda não foi confirmado."
        )
        await interaction.response.send_message(texto, ephemeral=True)
        return
    canal_entregas = interaction.guild.get_channel(cfg["loja"]["canal_entregas"])
    if not canal_entregas:
        await interaction.response.send_message(
            "⚠️ Defina o canal de entregas com `/configurar_loja canal_entregas:`.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "📸 Envie **aqui no canal** o print da troca (imagem). Você tem 5 minutos.", ephemeral=True
    )

    def confere(m: discord.Message) -> bool:
        return (
            m.author.id == interaction.user.id
            and m.channel.id == interaction.channel_id
            and any((a.content_type or "").startswith("image/") for a in m.attachments)
        )

    try:
        mensagem = await bot.wait_for("message", check=confere, timeout=300)
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "⏰ Tempo esgotado. Clique em Registrar entrega de novo.", ephemeral=True
        )
        return

    anexo = next(a for a in mensagem.attachments if (a.content_type or "").startswith("image/"))
    try:
        marcada = await asyncio.to_thread(marcar_imagem, await anexo.read())
    except Exception as e:
        print(f"[Entrega] erro ao marcar a imagem: {e}")
        await interaction.followup.send("⚠️ Não consegui processar essa imagem.", ephemeral=True)
        return

    cfg["loja"]["proof"] += 1
    salvar_settings()
    numero = cfg["loja"]["proof"]
    cliente = (carrinho.get("roblox") or {}).get("nome") or carrinho.get("roblox_nick", "?")
    pedido = carrinho.get("pedido", [])
    _, total, _ = texto_pedido(pedido)
    ts = int(datetime.now(timezone.utc).timestamp())

    await canal_entregas.send(
        view=container_prova(numero, cliente, interaction.user.id, pedido, total, ts),
        file=discord.File(io.BytesIO(marcada), filename="entrega.png"),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    atualizar_carrinho(interaction.channel_id, status="entregue", proof=numero)

    dono = interaction.guild.get_member(carrinho.get("dono", 0))
    await interaction.channel.send(
        f"✅ {dono.mention if dono else ''} entrega concluída! Obrigado por comprar na "
        f"**{cfg['loja']['nome']}** ♡ Quando quiser, é só fechar o ticket.",
        allowed_mentions=discord.AllowedMentions(users=True),
    )
    await interaction.followup.send(
        f"✅ Comprovante **PROOF {numero}** enviado em {canal_entregas.mention}.", ephemeral=True
    )
    await renomear_canal(interaction.channel, f"✅・entregue・{cliente}")


# /entregue: lançar entregas feitas fora do Discord (ex: TikTok)
def achar_item_estoque(texto: str):
    """Procura o item no estoque pelo nome (com ou sem emoji, sem diferenciar maiúscula)."""
    dados = carregar_estoque()
    alvo = texto.strip().lower()
    for cat in CATEGORIAS_ESTOQUE:
        for item in dados[cat]:
            if item["nome"].lower() == alvo or separar_emoji(item["nome"])[1].lower() == alvo:
                return item
    return None


def montar_item_entregue(texto: str, qtd: int):
    """Devolve (item do pedido, achou no estoque?). Fora do estoque o preço começa em 0."""
    item = achar_item_estoque(texto)
    if item:
        return {"nome": item["nome"], "qtd": qtd, "preco": item["preco"]}, True
    return {"nome": texto.strip(), "qtd": qtd, "preco": "0"}, False


async def autocompletar_item(interaction: discord.Interaction, atual: str):
    """Sugere os itens do estoque enquanto você digita no comando."""
    dados = carregar_estoque()
    opcoes = []
    for cat in CATEGORIAS_ESTOQUE:
        for item in dados[cat]:
            nome_limpo = separar_emoji(item["nome"])[1]
            if atual.lower() in nome_limpo.lower():
                opcoes.append(
                    app_commands.Choice(
                        name=f"{nome_limpo} ({item['qtd']}x • {item['preco']})"[:100],
                        value=item["nome"][:100],
                    )
                )
    return opcoes[:25]


@bot.tree.command(
    name="entregue",
    description="Registra uma entrega (dentro do ticket só precisa da foto)",
)
@app_commands.describe(
    foto="Print da troca (imagem)",
    nick="Nick do cliente no Roblox (só fora de ticket, ex: TikTok)",
    item="Item entregue (só fora de ticket)",
    quantidade="Quantidade do item",
    item2="Segundo item (opcional)",
    quantidade2="Quantidade do segundo item",
    item3="Terceiro item (opcional)",
    quantidade3="Quantidade do terceiro item",
    valor="Valor total cobrado, ex: 25,00 (obrigatório se o item não estiver no estoque)",
    origem="De onde veio a venda (aparece ao lado do nick)",
    baixar_estoque="Tirar a quantidade do estoque?",
)
@app_commands.autocomplete(item=autocompletar_item, item2=autocompletar_item, item3=autocompletar_item)
async def entregue(
    interaction: discord.Interaction,
    foto: discord.Attachment,
    nick: Optional[str] = None,
    item: Optional[str] = None,
    quantidade: app_commands.Range[int, 1, 99] = 1,
    item2: Optional[str] = None,
    quantidade2: app_commands.Range[int, 1, 99] = 1,
    item3: Optional[str] = None,
    quantidade3: app_commands.Range[int, 1, 99] = 1,
    valor: Optional[str] = None,
    origem: Optional[str] = "TikTok",
    baixar_estoque: bool = True,
):
    """Dentro de um ticket pago usa os dados do pedido. Fora de ticket usa o que você digitar."""
    if not eh_staff(interaction.user):
        await interaction.response.send_message("Só a staff pode lançar entregas.", ephemeral=True)
        return
    canal_entregas = interaction.guild.get_channel(cfg["loja"]["canal_entregas"])
    if not canal_entregas:
        await interaction.response.send_message(
            "⚠️ Defina o canal de entregas com `/configurar_loja canal_entregas:`.", ephemeral=True
        )
        return
    if not (foto.content_type or "").startswith("image/"):
        await interaction.response.send_message(
            "⚠️ A foto precisa ser uma imagem (png, jpg...).", ephemeral=True
        )
        return

    carrinho = ler_carrinho(interaction.channel_id)
    no_ticket = bool(carrinho.get("dono"))

    if no_ticket:
        if carrinho.get("status") == "entregue":
            await interaction.response.send_message(
                "Essa entrega já foi registrada.", ephemeral=True
            )
            return
        if carrinho.get("status") != "pago":
            await interaction.response.send_message(
                "O pagamento ainda não foi confirmado neste ticket.", ephemeral=True
            )
            return
    elif not nick or not item:
        await interaction.response.send_message(
            "Fora de um ticket você precisa preencher `nick` e `item`.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    faltaram = []

    if no_ticket:
        # Tudo vem do pedido do ticket (o estoque já foi baixado quando o pagamento foi confirmado)
        cliente = (carrinho.get("roblox") or {}).get("nome") or carrinho.get("roblox_nick", "?")
        pedido = carrinho.get("pedido", [])
        _, total, _ = texto_pedido(pedido)
    else:
        # Monta a lista de itens (até 3)
        pedido, fora_do_estoque = [], []
        for texto, qtd in ((item, quantidade), (item2, quantidade2), (item3, quantidade3)):
            if texto and texto.strip():
                linha, achou = montar_item_entregue(texto, qtd)
                pedido.append(linha)
                if not achou:
                    fora_do_estoque.append(texto.strip())

        if fora_do_estoque and not valor:
            await interaction.followup.send(
                "⚠️ Não achei no estoque: " + ", ".join(fora_do_estoque) + ".\n"
                "Preencha o campo `valor` com o valor total cobrado (ex: 25,00) e use o comando de novo.",
                ephemeral=True,
            )
            return

        # Valor digitado por você vale mais que o preço do estoque
        total_digitado = preco_para_float(valor) if valor else None
        if total_digitado is not None and len(pedido) == 1:
            pedido[0]["preco"] = moeda(total_digitado / pedido[0]["qtd"])
        _, total, _ = texto_pedido(pedido)
        if total_digitado is not None:
            total = total_digitado
        cliente = nick.strip() + (f" ({origem.strip()})" if origem and origem.strip() else "")

    try:
        marcada = await asyncio.to_thread(marcar_imagem, await foto.read())
    except Exception as e:
        print(f"[Entregue] erro ao marcar a imagem: {e}")
        await interaction.followup.send("⚠️ Não consegui processar essa imagem.", ephemeral=True)
        return

    if not no_ticket and baixar_estoque:
        faltaram = descontar_estoque(pedido)

    cfg["loja"]["proof"] += 1
    salvar_settings()
    numero = cfg["loja"]["proof"]
    ts = int(datetime.now(timezone.utc).timestamp())

    mensagem = await canal_entregas.send(
        view=container_prova(numero, cliente, interaction.user.id, pedido, total, ts),
        file=discord.File(io.BytesIO(marcada), filename="entrega.png"),
        allowed_mentions=discord.AllowedMentions.none(),
    )

    if no_ticket:
        atualizar_carrinho(interaction.channel_id, status="entregue", proof=numero)
        dono = interaction.guild.get_member(carrinho.get("dono", 0))
        await interaction.channel.send(
            f"✅ {dono.mention if dono else ''} entrega concluída! Obrigado por comprar na "
            f"**{cfg['loja']['nome']}** ♡ Quando quiser, é só fechar o ticket.",
            allowed_mentions=discord.AllowedMentions(users=True),
        )

    resposta = f"✅ Comprovante **PROOF {numero}** enviado em {canal_entregas.mention}.\n{mensagem.jump_url}"
    if faltaram:
        resposta += "\n⚠️ O estoque não tinha quantidade suficiente de: " + ", ".join(faltaram)
    await interaction.followup.send(resposta, ephemeral=True)

    if no_ticket:
        await renomear_canal(interaction.channel, f"✅・entregue・{cliente}")


# Configuração da loja por comando
@bot.tree.command(
    name="configurar_loja",
    description="Configura Pix, link do servidor, canal de entregas, conta do Roblox e logo",
)
@app_commands.describe(
    chave_pix="Sua chave Pix (telefone com +55, CPF, e-mail ou chave aleatória)",
    nome_pix="Nome de quem recebe o Pix (até 25 letras)",
    cidade_pix="Cidade de quem recebe (até 15 letras)",
    link_servidor="Link do servidor privado do Roblox onde as trocas acontecem",
    canal_entregas="Canal onde os comprovantes de entrega são enviados",
    roblox_loja="Usuário do Roblox da loja (quem manda o pedido de troca)",
    nome_loja="Nome da loja nos textos",
    logo="Imagem da logo (marca d'água do comprovante e centro do QR Code)",
)
async def configurar_loja(
    interaction: discord.Interaction,
    chave_pix: Optional[str] = None,
    nome_pix: Optional[str] = None,
    cidade_pix: Optional[str] = None,
    link_servidor: Optional[str] = None,
    canal_entregas: Optional[discord.TextChannel] = None,
    roblox_loja: Optional[str] = None,
    nome_loja: Optional[str] = None,
    logo: Optional[discord.Attachment] = None,
):
    if not eh_staff(interaction.user):
        await interaction.response.send_message("Só a staff pode usar isso.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)

    loja = cfg["loja"]
    if chave_pix:
        loja["pix_chave"] = chave_pix.strip()
    if nome_pix:
        loja["pix_nome"] = nome_pix.strip()
    if cidade_pix:
        loja["pix_cidade"] = cidade_pix.strip()
    if link_servidor:
        loja["link_servidor"] = link_servidor.strip()
    if canal_entregas:
        loja["canal_entregas"] = canal_entregas.id
    if roblox_loja:
        loja["roblox_loja"] = roblox_loja.strip()
        _cache_loja["dados"] = None
    if nome_loja:
        loja["nome"] = nome_loja.strip()
    aviso_logo = ""
    if logo:
        if (logo.content_type or "").startswith("image/"):
            await logo.save(LOGO_ARQUIVO)
            aviso_logo = "\n🖼️ Logo salva."
        else:
            aviso_logo = "\n⚠️ A logo precisa ser uma imagem."
    salvar_settings()

    chave = loja["pix_chave"]
    chave_mascarada = (chave[:3] + "•" * max(0, len(chave) - 5) + chave[-2:]) if len(chave) > 5 else chave
    canal = interaction.guild.get_channel(loja["canal_entregas"])
    await interaction.followup.send(
        "⚙️ **Configuração da loja**\n"
        f"• Loja: **{loja['nome']}**\n"
        f"• Pix: `{chave_mascarada or 'não definida'}` | {loja['pix_nome'] or 'sem nome'} | {loja['pix_cidade']}\n"
        f"• Roblox da loja: `{loja['roblox_loja']}`\n"
        f"• Link do servidor: {loja['link_servidor'] or 'não definido'}\n"
        f"• Canal de entregas: {canal.mention if canal else 'não definido'}\n"
        f"• Logo: {'salva' if LOGO_ARQUIVO.exists() else 'não definida'}" + aviso_logo,
        ephemeral=True,
    )


# --- Painel público ---
class PainelView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

        comprar = criar_botao("comprar", "painel:comprar")
        comprar.callback = self.abrir_formulario
        estoque = criar_botao("estoque", "painel:estoque")
        estoque.callback = self.ver_estoque

        c = montar_container("painel", {})
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.ActionRow(comprar, estoque))
        self.add_item(c)

    async def abrir_formulario(self, interaction: discord.Interaction):
        await abrir_carrinho(interaction)

    async def ver_estoque(self, interaction: discord.Interaction):
        view = discord.ui.LayoutView()
        view.add_item(container_estoque())
        await interaction.response.send_message(view=view, ephemeral=True)


# --- Painel de suporte e venda (menu de opções) ---
def criar_menu_suporte(custom_id: Optional[str] = None, desativado: bool = False):
    m = cfg["menu_suporte"]
    extras = {"custom_id": custom_id} if custom_id else {}
    return discord.ui.Select(
        placeholder=m["placeholder"],
        disabled=desativado,
        options=[
            discord.SelectOption(
                label=o["label"],
                value=k,
                description=o["descricao"] or None,
                emoji=o["emoji"] or None,
            )
            for k, o in m["opcoes"].items()
        ],
        **extras,
    )


class SuporteModal(discord.ui.Modal, title="Suporte"):
    assunto = discord.ui.TextInput(
        label="Descreva o que você precisa",
        style=discord.TextStyle.paragraph,
        placeholder="Explique seu problema ou dúvida...",
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await abrir_ticket(interaction, "suporte", {"assunto": self.assunto.value.strip()})


class VendaModal(discord.ui.Modal, title="Vender item de MM2"):
    item = discord.ui.TextInput(label="Qual item você quer vender?", max_length=100)
    preco = discord.ui.TextInput(
        label="Quanto você quer receber?", placeholder="Ex: R$ 20,00", max_length=50
    )
    nick = discord.ui.TextInput(label="Seu Nick no Roblox", min_length=3, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        await abrir_ticket(
            interaction,
            "venda",
            {
                "item": self.item.value.strip(),
                "preco": self.preco.value.strip(),
                "nick": self.nick.value.strip(),
            },
        )


class PainelSuporteView(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        menu = criar_menu_suporte("painel_suporte:menu")
        menu.callback = self.escolher

        c = montar_container("painel_suporte", {})
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.ActionRow(menu))
        self.add_item(c)

    async def escolher(self, interaction: discord.Interaction):
        valor = interaction.data["values"][0]
        if valor == "venda":
            await interaction.response.send_modal(VendaModal())
        else:
            await interaction.response.send_modal(SuporteModal())
        # Recarrega o painel para o menu voltar ao texto original (permite escolher de novo)
        try:
            await interaction.message.edit(view=PainelSuporteView())
        except Exception:
            pass


# --- Painel de estoque (só para a staff) ---
class ItemModal(discord.ui.Modal):
    def __init__(self, cat: str, idx: Optional[int] = None, item: Optional[dict] = None):
        super().__init__(title="Editar item" if item else "Adicionar item")
        self.cat = cat
        self.idx = idx
        self.nome = discord.ui.TextInput(
            label="Nome do item", default=item["nome"] if item else None, max_length=80
        )
        self.qtd = discord.ui.TextInput(
            label="Quantidade", default=str(item["qtd"]) if item else "1", max_length=5
        )
        self.preco = discord.ui.TextInput(
            label="Preço (ex: R$ 15,00)", default=item["preco"] if item else None, max_length=30
        )
        self.add_item(self.nome)
        self.add_item(self.qtd)
        self.add_item(self.preco)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            qtd = max(0, int(self.qtd.value))
        except ValueError:
            await interaction.response.send_message(
                "⚠️ A quantidade precisa ser um número.", ephemeral=True
            )
            return

        dados = carregar_estoque()
        novo = {"nome": self.nome.value.strip(), "qtd": qtd, "preco": self.preco.value.strip()}
        if self.idx is None:
            dados[self.cat].append(novo)
            idx = len(dados[self.cat]) - 1
        else:
            dados[self.cat][self.idx] = novo
            idx = self.idx
        salvar_estoque(dados)
        await interaction.response.edit_message(view=EstoqueAdminView((self.cat, idx)))


class ConfirmarLimparView(discord.ui.View):
    """Pergunta de segurança antes de apagar o estoque inteiro."""

    def __init__(self, painel: discord.Interaction):
        super().__init__(timeout=30)
        self.painel = painel

    @discord.ui.button(label="Sim, limpar tudo", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def sim(self, interaction: discord.Interaction, botao: discord.ui.Button):
        if not eh_staff(interaction.user):
            await interaction.response.send_message("Só a staff pode fazer isso.", ephemeral=True)
            return
        if ESTOQUE_ARQUIVO.exists():  # guarda uma cópia, caso você limpe sem querer
            Path("estoque_backup.json").write_text(
                ESTOQUE_ARQUIVO.read_text(encoding="utf-8"), encoding="utf-8"
            )
        salvar_estoque({"godlys": [], "sets": []})
        await interaction.response.edit_message(
            content="✅ Estoque limpo. (Cópia antiga salva em `estoque_backup.json`)", view=None
        )
        try:
            await self.painel.edit_original_response(view=EstoqueAdminView())
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def nao(self, interaction: discord.Interaction, botao: discord.ui.Button):
        await interaction.response.edit_message(content="Cancelado, nada foi apagado.", view=None)


class EstoqueAdminView(discord.ui.LayoutView):
    def __init__(self, selecionado: Optional[tuple] = None):
        super().__init__(timeout=600)
        dados = carregar_estoque()

        if selecionado and selecionado[1] >= len(dados[selecionado[0]]):
            selecionado = None

        c = discord.ui.Container(accent_colour=COR_PADRAO)
        c.add_item(
            discord.ui.TextDisplay(
                "# 📦 Gerenciar estoque\n"
                "Escolha um item nos menus para editar ou clique para adicionar um novo."
            )
        )

        for chave, titulo in categorias():
            lista = dados[chave]
            linhas = (
                "\n".join(f"• {i['nome']} — {i['qtd']}x — {i['preco']}" for i in lista)[:1500]
                if lista
                else "*vazio*"
            )
            c.add_item(discord.ui.Separator())
            c.add_item(discord.ui.TextDisplay(f"## {titulo}\n{linhas}"))

        if selecionado:
            cat, idx = selecionado
            item = dados[cat][idx]
            c.add_item(discord.ui.Separator())
            c.add_item(
                discord.ui.TextDisplay(
                    f"### ✏️ Editando: {item['nome']}\n"
                    f"Quantidade: **{item['qtd']}** • Preço: **{item['preco']}**"
                )
            )
            menos = discord.ui.Button(label="-1", style=discord.ButtonStyle.danger)
            mais = discord.ui.Button(label="+1", style=discord.ButtonStyle.success)
            editar = discord.ui.Button(label="Editar", style=discord.ButtonStyle.primary)
            remover = discord.ui.Button(
                label="Remover", emoji="🗑️", style=discord.ButtonStyle.secondary
            )
            menos.callback = self._ajustar(cat, idx, -1)
            mais.callback = self._ajustar(cat, idx, +1)
            editar.callback = self._editar(cat, idx)
            remover.callback = self._remover(cat, idx)
            c.add_item(discord.ui.ActionRow(menos, mais, editar, remover))

        add_godly = discord.ui.Button(
            label="Adicionar Godly", emoji="➕", style=discord.ButtonStyle.success
        )
        add_set = discord.ui.Button(
            label="Adicionar Set", emoji="➕", style=discord.ButtonStyle.success
        )
        limpar = discord.ui.Button(
            label="Limpar Estoque", emoji="🗑️", style=discord.ButtonStyle.danger
        )
        add_godly.callback = self._adicionar("godlys")
        add_set.callback = self._adicionar("sets")
        limpar.callback = self._limpar
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.ActionRow(add_godly, add_set, limpar))

        for chave, titulo in categorias():
            lista = dados[chave]
            if not lista:
                continue
            opcoes = [
                discord.SelectOption(
                    label=i["nome"][:100],
                    value=str(n),
                    description=f"{i['qtd']}x • {i['preco']}"[:100],
                )
                for n, i in enumerate(lista[:25])
            ]
            menu = discord.ui.Select(placeholder=f"Escolher em {titulo}...", options=opcoes)
            menu.callback = self._escolher(chave, menu)
            c.add_item(discord.ui.ActionRow(menu))

        self.add_item(c)

    async def _limpar(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⚠️ **Limpar todo o estoque?** Isso apaga todos os godlys e sets.",
            view=ConfirmarLimparView(interaction),
            ephemeral=True,
        )

    def _escolher(self, cat, menu):
        async def cb(interaction: discord.Interaction):
            await interaction.response.edit_message(
                view=EstoqueAdminView((cat, int(menu.values[0])))
            )

        return cb

    def _ajustar(self, cat, idx, delta):
        async def cb(interaction: discord.Interaction):
            dados = carregar_estoque()
            item = dados[cat][idx]
            item["qtd"] = max(0, item["qtd"] + delta)
            salvar_estoque(dados)
            await interaction.response.edit_message(view=EstoqueAdminView((cat, idx)))

        return cb

    def _editar(self, cat, idx):
        async def cb(interaction: discord.Interaction):
            item = carregar_estoque()[cat][idx]
            await interaction.response.send_modal(ItemModal(cat, idx, item))

        return cb

    def _remover(self, cat, idx):
        async def cb(interaction: discord.Interaction):
            dados = carregar_estoque()
            dados[cat].pop(idx)
            salvar_estoque(dados)
            await interaction.response.edit_message(view=EstoqueAdminView(None))

        return cb

    def _adicionar(self, cat):
        async def cb(interaction: discord.Interaction):
            await interaction.response.send_modal(ItemModal(cat))

        return cb


# --- Painel /personalizar (edita os containers por comando) ---
class TextoModal(discord.ui.Modal):
    def __init__(self, chave: str):
        super().__init__(title="Editar texto do container")
        self.chave = chave
        d = cfg["containers"][chave]
        self.titulo = discord.ui.TextInput(
            label="Título (deixe vazio para não ter)",
            default=d["titulo"] or None,
            required=False,
            max_length=200,
        )
        self.texto = discord.ui.TextInput(
            label="Texto (--- sozinho na linha = separador)",
            style=discord.TextStyle.paragraph,
            default=d["texto"] or None,
            required=False,
            max_length=3000,
        )
        self.add_item(self.titulo)
        self.add_item(self.texto)

    async def on_submit(self, interaction: discord.Interaction):
        cfg["containers"][self.chave]["titulo"] = self.titulo.value.strip()
        cfg["containers"][self.chave]["texto"] = self.texto.value
        salvar_settings()
        await interaction.response.edit_message(view=PersonalizarView(self.chave))
        if self.chave in ("painel", "painel_suporte"):
            await atualizar_painel(self.chave)


class CorImagemModal(discord.ui.Modal):
    def __init__(self, chave: str):
        super().__init__(title="Cor e imagem do container")
        self.chave = chave
        d = cfg["containers"][chave]
        self.cor = discord.ui.TextInput(
            label="Cor em hex (ex: #5865F2)", default=d["cor"], max_length=7
        )
        self.imagem = discord.ui.TextInput(
            label="Link da imagem grande (vazio = sem imagem)",
            default=d["imagem"] or None,
            required=False,
            max_length=500,
        )
        self.add_item(self.cor)
        self.add_item(self.imagem)

    async def on_submit(self, interaction: discord.Interaction):
        if not cor_valida(self.cor.value):
            await interaction.response.send_message(
                "⚠️ Cor inválida. Use o formato #RRGGBB, por exemplo #5865F2.", ephemeral=True
            )
            return
        imagem = self.imagem.value.strip()
        if imagem and not imagem.startswith("http"):
            await interaction.response.send_message(
                "⚠️ O link da imagem precisa começar com http.", ephemeral=True
            )
            return
        cfg["containers"][self.chave]["cor"] = "#" + self.cor.value.strip().lstrip("#").upper()
        cfg["containers"][self.chave]["imagem"] = imagem
        salvar_settings()
        await interaction.response.edit_message(view=PersonalizarView(self.chave))
        if self.chave in ("painel", "painel_suporte"):
            await atualizar_painel(self.chave)


class SecoesModal(discord.ui.Modal, title="Títulos do estoque"):
    def __init__(self):
        super().__init__()
        s = cfg["secoes"]
        self.godlys = discord.ui.TextInput(label="Título da seção Godlys", default=s["godlys"], max_length=60)
        self.sets = discord.ui.TextInput(label="Título da seção Sets", default=s["sets"], max_length=60)
        self.vazio = discord.ui.TextInput(
            label="Texto quando não tem nada no estoque", default=s["vazio"], max_length=200
        )
        self.add_item(self.godlys)
        self.add_item(self.sets)
        self.add_item(self.vazio)

    async def on_submit(self, interaction: discord.Interaction):
        cfg["secoes"] = {
            "godlys": self.godlys.value.strip(),
            "sets": self.sets.value.strip(),
            "vazio": self.vazio.value.strip(),
        }
        salvar_settings()
        await interaction.response.edit_message(view=PersonalizarView("estoque"))


class RobloxErroModal(discord.ui.Modal, title="Texto quando o nick não existe"):
    def __init__(self):
        super().__init__()
        self.texto = discord.ui.TextInput(
            label="Texto (pode usar {nick})",
            style=discord.TextStyle.paragraph,
            default=cfg["roblox_erro"],
            max_length=1000,
        )
        self.add_item(self.texto)

    async def on_submit(self, interaction: discord.Interaction):
        cfg["roblox_erro"] = self.texto.value
        salvar_settings()
        await interaction.response.edit_message(view=PersonalizarView("roblox"))


class BotaoModal(discord.ui.Modal):
    def __init__(self, chave: str):
        super().__init__(title=f"Botão: {BOTOES_NOMES[chave]}")
        self.chave = chave
        b = cfg["botoes"][chave]
        self.label = discord.ui.TextInput(label="Texto do botão", default=b["label"], max_length=80)
        self.emoji = discord.ui.TextInput(
            label="Emoji (opcional)", default=b["emoji"] or None, required=False, max_length=60
        )
        self.estilo = discord.ui.TextInput(
            label="Cor: azul, cinza, verde ou vermelho",
            default=ESTILOS_INV.get(b["estilo"], "azul"),
            max_length=10,
        )
        self.add_item(self.label)
        self.add_item(self.emoji)
        self.add_item(self.estilo)

    async def on_submit(self, interaction: discord.Interaction):
        valor = self.estilo.value.strip().lower()
        estilo_final = ESTILOS.get(valor) or (valor if valor in ESTILOS.values() else None)
        if not estilo_final:
            await interaction.response.send_message(
                "⚠️ Cor do botão inválida. Use: azul, cinza, verde ou vermelho.", ephemeral=True
            )
            return
        if not emoji_valido(self.emoji.value.strip()):
            await interaction.response.send_message(
                "⚠️ Emoji inválido. Use um emoji normal ou um personalizado no formato <:nome:id>.",
                ephemeral=True,
            )
            return
        cfg["botoes"][self.chave] = {
            "label": self.label.value.strip(),
            "emoji": self.emoji.value.strip(),
            "estilo": estilo_final,
        }
        salvar_settings()
        atual = "painel" if self.chave in ("comprar", "estoque") else "boas_vindas"
        await interaction.response.edit_message(view=PersonalizarView(atual))
        if self.chave in ("comprar", "estoque"):
            await atualizar_painel("painel")


class PlaceholderModal(discord.ui.Modal, title="Texto do menu"):
    def __init__(self):
        super().__init__()
        self.campo = discord.ui.TextInput(
            label="Texto que aparece no menu fechado",
            default=cfg["menu_suporte"]["placeholder"],
            max_length=100,
        )
        self.add_item(self.campo)

    async def on_submit(self, interaction: discord.Interaction):
        cfg["menu_suporte"]["placeholder"] = self.campo.value.strip()
        salvar_settings()
        await interaction.response.edit_message(view=PersonalizarView("painel_suporte"))
        await atualizar_painel("painel_suporte")


class OpcaoModal(discord.ui.Modal, title="Opção do menu"):
    def __init__(self, chave: str):
        super().__init__()
        self.chave = chave
        o = cfg["menu_suporte"]["opcoes"][chave]
        self.nome = discord.ui.TextInput(label="Nome da opção", default=o["label"], max_length=100)
        self.descricao = discord.ui.TextInput(
            label="Descrição (opcional)", default=o["descricao"] or None, required=False, max_length=100
        )
        self.emoji_campo = discord.ui.TextInput(
            label="Emoji (opcional)", default=o["emoji"] or None, required=False, max_length=60
        )
        self.add_item(self.nome)
        self.add_item(self.descricao)
        self.add_item(self.emoji_campo)

    async def on_submit(self, interaction: discord.Interaction):
        emoji = self.emoji_campo.value.strip()
        if not emoji_valido(emoji):
            await interaction.response.send_message(
                "⚠️ Emoji inválido. Use um emoji normal ou um personalizado no formato <:nome:id>.",
                ephemeral=True,
            )
            return
        cfg["menu_suporte"]["opcoes"][self.chave] = {
            "label": self.nome.value.strip(),
            "descricao": self.descricao.value.strip(),
            "emoji": emoji,
        }
        salvar_settings()
        await interaction.response.edit_message(view=PersonalizarView("painel_suporte"))
        await atualizar_painel("painel_suporte")


class PersonalizarView(discord.ui.LayoutView):
    def __init__(self, chave: str = "painel"):
        super().__init__(timeout=900)
        meta = CONTAINERS[chave]

        menu = discord.ui.Select(
            placeholder="Escolha o container...",
            options=[
                discord.SelectOption(label=m["nome"], value=k, default=(k == chave))
                for k, m in CONTAINERS.items()
            ],
        )

        async def trocar(interaction: discord.Interaction):
            await interaction.response.edit_message(view=PersonalizarView(menu.values[0]))

        menu.callback = trocar

        btn_texto = discord.ui.Button(label="Editar texto", emoji="📝", style=discord.ButtonStyle.primary)
        btn_cor = discord.ui.Button(label="Cor e imagem", emoji="🎨", style=discord.ButtonStyle.secondary)
        btn_reset = discord.ui.Button(label="Resetar", emoji="♻️", style=discord.ButtonStyle.danger)

        async def abrir_texto(interaction):
            await interaction.response.send_modal(TextoModal(chave))

        async def abrir_cor(interaction):
            await interaction.response.send_modal(CorImagemModal(chave))

        async def fazer_reset(interaction):
            resetar(chave)
            await interaction.response.edit_message(view=PersonalizarView(chave))
            if chave in ("painel", "painel_suporte"):
                await atualizar_painel(chave)

        btn_texto.callback = abrir_texto
        btn_cor.callback = abrir_cor
        btn_reset.callback = fazer_reset
        linha = [btn_texto, btn_cor]

        if chave == "estoque":
            btn_secoes = discord.ui.Button(label="Títulos das listas", emoji="📑", style=discord.ButtonStyle.secondary)

            async def abrir_secoes(interaction):
                await interaction.response.send_modal(SecoesModal())

            btn_secoes.callback = abrir_secoes
            linha.append(btn_secoes)
        elif chave == "roblox":
            btn_erro = discord.ui.Button(label="Texto de erro", emoji="⚠️", style=discord.ButtonStyle.secondary)

            async def abrir_erro(interaction):
                await interaction.response.send_modal(RobloxErroModal())

            btn_erro.callback = abrir_erro
            linha.append(btn_erro)
        elif chave == "painel_suporte":
            btn_ph = discord.ui.Button(label="Texto do menu", emoji="🔽", style=discord.ButtonStyle.secondary)

            async def abrir_ph(interaction):
                await interaction.response.send_modal(PlaceholderModal())

            btn_ph.callback = abrir_ph
            linha.append(btn_ph)
        linha.append(btn_reset)

        menu_botao = discord.ui.Select(
            placeholder="Editar um botão (texto, emoji, cor)...",
            options=[
                discord.SelectOption(label=nome, value=k) for k, nome in BOTOES_NOMES.items()
            ],
        )

        async def abrir_botao(interaction: discord.Interaction):
            await interaction.response.send_modal(BotaoModal(menu_botao.values[0]))

        menu_botao.callback = abrir_botao

        menu_opcao = None
        if chave == "painel_suporte":
            menu_opcao = discord.ui.Select(
                placeholder="Editar uma opção do menu...",
                options=[
                    discord.SelectOption(label=o["label"][:100], value=k)
                    for k, o in cfg["menu_suporte"]["opcoes"].items()
                ],
            )

            async def abrir_opcao(interaction: discord.Interaction):
                await interaction.response.send_modal(OpcaoModal(menu_opcao.values[0]))

            menu_opcao.callback = abrir_opcao

        c = discord.ui.Container(accent_colour=COR_PADRAO)
        c.add_item(
            discord.ui.TextDisplay(
                "# 🎨 Personalizar containers\n"
                "Escolha o container, edite e veja a prévia logo abaixo."
            )
        )
        c.add_item(discord.ui.ActionRow(menu))
        c.add_item(discord.ui.Separator())
        c.add_item(
            discord.ui.TextDisplay(
                f"**Editando:** {meta['nome']}\n"
                f"**Variáveis para usar no texto:** {meta['vars']}\n"
                f"-# {meta['obs']}\n"
                "-# Dica: escreva --- numa linha sozinha no texto para criar uma linha separadora."
            )
        )
        c.add_item(discord.ui.ActionRow(*linha))
        c.add_item(discord.ui.ActionRow(menu_botao))
        if menu_opcao:
            c.add_item(discord.ui.ActionRow(menu_opcao))
        self.add_item(c)

        self.add_item(discord.ui.TextDisplay("-# 👇 Prévia"))
        if chave == "estoque":
            self.add_item(container_estoque())
        elif chave == "painel_suporte":
            previa = montar_container(chave, VARS_EXEMPLO)
            previa.add_item(discord.ui.Separator())
            previa.add_item(discord.ui.ActionRow(criar_menu_suporte(desativado=True)))
            self.add_item(previa)
        else:
            self.add_item(montar_container(chave, VARS_EXEMPLO))


# --- Mensagem personalizada (container solto, em qualquer canal) ---
class MensagemModal(discord.ui.Modal, title="Criar mensagem"):
    titulo = discord.ui.TextInput(label="Título", required=False, max_length=200)
    texto = discord.ui.TextInput(
        label="Texto (--- sozinho na linha = separador)",
        style=discord.TextStyle.paragraph,
        max_length=3000,
    )
    cor = discord.ui.TextInput(label="Cor em hex (ex: #5865F2)", required=False, max_length=7)
    imagem = discord.ui.TextInput(
        label="Link da imagem grande (opcional)", required=False, max_length=500
    )
    rodape = discord.ui.TextInput(label="Rodapé (opcional)", required=False, max_length=200)

    def __init__(self, canal: discord.TextChannel):
        super().__init__()
        self.canal = canal

    async def on_submit(self, interaction: discord.Interaction):
        c = discord.ui.Container(accent_colour=parse_cor(self.cor.value or "#5865F2"))
        cabecalho = f"# {self.titulo.value}\n" if self.titulo.value else ""
        blocos = dividir_blocos(cabecalho + self.texto.value)
        c.add_item(discord.ui.TextDisplay(blocos[0]))
        for extra in blocos[1:]:
            c.add_item(discord.ui.Separator())
            c.add_item(discord.ui.TextDisplay(extra))
        if self.imagem.value.strip().startswith("http"):
            for item in banner(self.imagem.value.strip()):
                c.add_item(item)
        if self.rodape.value:
            c.add_item(discord.ui.Separator())
            c.add_item(discord.ui.TextDisplay(f"-# {self.rodape.value}"))

        view = discord.ui.LayoutView()
        view.add_item(c)
        try:
            await self.canal.send(view=view)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"⚠️ Não consegui enviar: {e}", ephemeral=True)
            return
        await interaction.response.send_message(
            f"✅ Mensagem enviada em {self.canal.mention}", ephemeral=True
        )


# --- Comandos ---
def mencao(prefixo: str, id_: int) -> str:
    return f"<{prefixo}{id_}>" if id_ else "*não definido*"


@bot.tree.command(name="configurar", description="Define categoria dos tickets, cargo atendente e logs")
@app_commands.describe(
    categoria="Categoria onde os tickets de compra serão criados",
    categoria_suporte="Categoria dos tickets de suporte/venda (se vazio, usa a mesma)",
    cargo="Cargo de atendente (é marcado e vê os tickets)",
    logs="Canal da staff que recebe o transcript",
    transcript_na_dm="Mandar o transcript também na DM de quem abriu?",
)
@app_commands.default_permissions(administrator=True)
async def configurar(
    interaction: discord.Interaction,
    categoria: Optional[discord.CategoryChannel] = None,
    categoria_suporte: Optional[discord.CategoryChannel] = None,
    cargo: Optional[discord.Role] = None,
    logs: Optional[discord.TextChannel] = None,
    transcript_na_dm: Optional[bool] = None,
):
    if categoria:
        cfg["ids"]["categoria"] = categoria.id
    if categoria_suporte:
        cfg["ids"]["categoria_suporte"] = categoria_suporte.id
    if cargo:
        cfg["ids"]["cargo"] = cargo.id
    if logs:
        cfg["ids"]["logs"] = logs.id
    if transcript_na_dm is not None:
        cfg["ids"]["dm"] = transcript_na_dm
    salvar_settings()

    i = cfg["ids"]
    c = discord.ui.Container(accent_colour=COR_PADRAO)
    c.add_item(
        discord.ui.TextDisplay(
            "# ⚙️ Configuração atual\n"
            f"**Categoria (compra):** {mencao('#', i['categoria'])}\n"
            f"**Categoria (suporte/venda):** {mencao('#', i['categoria_suporte'])}\n"
            f"**Cargo atendente:** {mencao('@&', i['cargo'])}\n"
            f"**Canal de logs:** {mencao('#', i['logs'])}\n"
            f"**Transcript na DM:** {'sim' if i['dm'] else 'não'}\n"
            "-# Use /configurar de novo com só o campo que quiser mudar."
        )
    )
    view = discord.ui.LayoutView()
    view.add_item(c)
    await interaction.response.send_message(view=view, ephemeral=True)


@bot.tree.command(name="personalizar", description="Edita texto, cor, imagem e botões dos containers")
@app_commands.default_permissions(administrator=True)
async def personalizar(interaction: discord.Interaction):
    await interaction.response.send_message(view=PersonalizarView("painel"), ephemeral=True)


@bot.tree.command(name="painel", description="Envia o painel de tickets neste canal")
@app_commands.default_permissions(administrator=True)
async def painel(interaction: discord.Interaction):
    msg = await interaction.channel.send(view=PainelView())
    cfg["painel_msg"] = [msg.channel.id, msg.id]
    salvar_settings()
    await interaction.response.send_message("✅ Painel enviado!", ephemeral=True)


@bot.tree.command(name="painel_suporte", description="Envia o painel de suporte/venda neste canal")
@app_commands.default_permissions(administrator=True)
async def painel_suporte(interaction: discord.Interaction):
    msg = await interaction.channel.send(view=PainelSuporteView())
    cfg["painel_suporte_msg"] = [msg.channel.id, msg.id]
    salvar_settings()
    await interaction.response.send_message("✅ Painel de suporte enviado!", ephemeral=True)


@bot.tree.command(name="estoque", description="Abre o painel para gerenciar o estoque")
async def estoque(interaction: discord.Interaction):
    if not eh_staff(interaction.user):
        await interaction.response.send_message("Só a staff pode usar isso.", ephemeral=True)
        return
    await interaction.response.send_message(view=EstoqueAdminView(), ephemeral=True)


# --- Importar estoque de um arquivo .json ---
CATEGORIAS_ESTOQUE = ("godlys", "sets")


def normalizar_importacao(bruto) -> dict:
    """Valida o .json enviado e devolve {'godlys': [...], 'sets': [...]} já limpo."""
    if not isinstance(bruto, dict):
        raise ValueError("O arquivo precisa ser um objeto com \"godlys\" e/ou \"sets\".")
    resultado = {}
    for cat in CATEGORIAS_ESTOQUE:
        itens = []
        lista = bruto.get(cat, [])
        if not isinstance(lista, list):
            raise ValueError(f"\"{cat}\" precisa ser uma lista.")
        if cat == "godlys":  # facas e pistolas também entram em godlys
            for extra in ("facas", "pistolas"):
                mais = bruto.get(extra, [])
                if not isinstance(mais, list):
                    raise ValueError(f"\"{extra}\" precisa ser uma lista.")
                lista = lista + mais
        for n, item in enumerate(lista, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"{cat}: o item {n} está em formato errado.")
            nome = str(item.get("nome", "")).strip()
            if not nome:
                raise ValueError(f"{cat}: o item {n} está sem nome.")
            emoji = str(item.get("emoji", "")).strip()
            if emoji and not nome.startswith(emoji):
                nome = f"{emoji} {nome}"
            try:
                qtd = max(0, int(item.get("qtd", 0)))
            except (TypeError, ValueError):
                raise ValueError(f"{cat}: \"{nome}\" tem quantidade inválida.")
            preco = item.get("preco", "0")
            if isinstance(preco, (int, float)):
                preco = f"{preco:.2f}".replace(".", ",")
            else:
                preco = str(preco).replace("R$", "").strip()
            itens.append({"nome": nome, "qtd": qtd, "preco": preco})
        resultado[cat] = itens
    return resultado


def aplicar_importacao(atual: dict, novo: dict, modo: str):
    """Junta o que veio do arquivo no estoque. Devolve (estoque, adicionados, atualizados)."""
    adicionados = atualizados = 0
    if modo == "substituir":
        total = sum(len(v) for v in novo.values())
        return {cat: novo[cat] for cat in CATEGORIAS_ESTOQUE}, total, 0

    def nome_limpo(item):
        return separar_emoji(item["nome"])[1].lower()

    for cat in CATEGORIAS_ESTOQUE:
        for item in novo[cat]:
            # procura o item em qualquer categoria (compara o nome sem o emoji)
            achado = None
            for cat_antiga in CATEGORIAS_ESTOQUE:
                for velho in atual[cat_antiga]:
                    if nome_limpo(velho) == nome_limpo(item):
                        achado = (cat_antiga, velho)
                        break
                if achado:
                    break

            if not achado:
                atual[cat].append(item)
                adicionados += 1
                continue

            cat_antiga, velho = achado
            qtd = velho["qtd"] + item["qtd"] if modo == "somar" else item["qtd"]
            velho.update({"nome": item["nome"], "qtd": qtd, "preco": item["preco"]})
            if cat_antiga != cat:  # mudou de categoria: move pro lugar certo
                atual[cat_antiga].remove(velho)
                atual[cat].append(velho)
            atualizados += 1
    return atual, adicionados, atualizados


@bot.tree.command(name="importar_estoque", description="Lê um arquivo .json e coloca os itens no estoque")
@app_commands.describe(
    arquivo="Arquivo .json com os itens (godlys e sets)",
    modo="O que fazer com itens que já existem no estoque",
)
@app_commands.choices(
    modo=[
        app_commands.Choice(name="Atualizar (troca qtd e preço dos que já existem)", value="atualizar"),
        app_commands.Choice(name="Somar (soma a quantidade nos que já existem)", value="somar"),
        app_commands.Choice(name="Substituir tudo (apaga o estoque atual)", value="substituir"),
    ]
)
async def importar_estoque(
    interaction: discord.Interaction,
    arquivo: discord.Attachment,
    modo: app_commands.Choice[str],
):
    if not eh_staff(interaction.user):
        await interaction.response.send_message("Só a staff pode usar isso.", ephemeral=True)
        return
    if not arquivo.filename.lower().endswith(".json"):
        await interaction.response.send_message("Envie um arquivo .json.", ephemeral=True)
        return
    if arquivo.size > 1_000_000:
        await interaction.response.send_message("Arquivo grande demais (máx. 1 MB).", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    try:
        texto = (await arquivo.read()).decode("utf-8-sig")  # utf-8-sig aceita arquivo salvo pelo Bloco de Notas
        novo = normalizar_importacao(json.loads(texto))
    except json.JSONDecodeError as e:
        await interaction.followup.send(
            f"⚠️ O JSON está com erro na linha {e.lineno}, coluna {e.colno}: {e.msg}", ephemeral=True
        )
        return
    except (ValueError, UnicodeDecodeError) as e:
        await interaction.followup.send(f"⚠️ {e}", ephemeral=True)
        return

    atual, adicionados, atualizados = aplicar_importacao(carregar_estoque(), novo, modo.value)
    salvar_estoque(atual)
    await interaction.followup.send(
        f"✅ Estoque importado ({modo.name.split(' (')[0]}): "
        f"**{adicionados}** adicionados, **{atualizados}** atualizados.\n"
        f"Agora são {len(atual['godlys'])} godlys e {len(atual['sets'])} sets.",
        ephemeral=True,
    )


def mensagens_stoq() -> list:
    """Estoque disponível em texto simples, no estilo - ( emoji ) `8 un. Nome - R$ 0,00`.
    Divide em várias mensagens se passar do limite de 2000 caracteres do Discord."""
    dados = carregar_estoque()
    blocos = []
    for chave, titulo in categorias():
        disponiveis = [i for i in dados[chave] if i["qtd"] > 0]
        if not disponiveis:
            continue  # seção sem item disponível não aparece
        bloco = f"## {titulo}"
        for item in sorted(disponiveis, key=lambda i: preco_para_float(i["preco"]), reverse=True):
            linha = linha_estoque(item)
            if len(bloco) + len(linha) + 1 > 1900:
                blocos.append(bloco)
                bloco = f"## {titulo} (cont.)"
            bloco += "\n" + linha
        blocos.append(bloco)

    mensagens, atual = [], ""
    for bloco in blocos:
        if atual and len(atual) + 1 + len(bloco) > 2000:
            mensagens.append(atual)
            atual = bloco
        else:
            atual = f"{atual}\n{bloco}" if atual else bloco
    if atual:
        mensagens.append(atual)
    return mensagens


@bot.tree.command(name="stoq", description="Mostra o estoque disponível")
async def stoq(interaction: discord.Interaction):
    mensagens = mensagens_stoq() or [cfg["secoes"]["vazio"]]
    sem_mencao = discord.AllowedMentions.none()
    await interaction.response.send_message(mensagens[0], allowed_mentions=sem_mencao)
    for texto in mensagens[1:]:
        await interaction.followup.send(texto, allowed_mentions=sem_mencao)


@bot.tree.command(name="mensagem", description="Envia uma mensagem personalizada em container")
@app_commands.describe(canal="Canal onde a mensagem será enviada")
@app_commands.default_permissions(administrator=True)
async def mensagem(interaction: discord.Interaction, canal: discord.TextChannel):
    await interaction.response.send_modal(MensagemModal(canal))


# --- Inicialização do bot ---
@bot.event
async def setup_hook():
    # Faz os botões continuarem funcionando depois de reiniciar o bot
    bot.add_view(PainelView())
    bot.add_view(TicketView())
    bot.add_view(PainelSuporteView())
    bot.add_view(CarrinhoEscolherView())
    bot.add_view(CarrinhoResumoView())
    bot.add_view(CarrinhoPagamentoView())
    bot.add_view(CarrinhoPerfilView())
    bot.add_view(CarrinhoPixView())
    bot.add_view(CarrinhoEntregaView())

    guild_id = os.getenv("GUILD_ID")
    if guild_id:
        servidor = discord.Object(id=int(guild_id))
        bot.tree.copy_global_to(guild=servidor)
        await bot.tree.sync(guild=servidor)
    else:
        await bot.tree.sync()


@bot.event
async def on_guild_channel_delete(canal):
    # Apaga o carrinho salvo quando o canal some
    dados = carregar_carrinhos()
    if str(canal.id) in dados:
        del dados[str(canal.id)]
        salvar_carrinhos(dados)


@bot.event
async def on_ready():
    print(f"✅ Bot online como {bot.user}")


bot.run(os.getenv("DISCORD_TOKEN"))
