import socket
import threading
import time
import json
import os
import sys
from datetime import datetime

HOST = "127.0.0.1"
PORT = 65432
ARQ_DADOS = "usuarios_leilao.json"

lock = threading.Lock()
encerrar_servidor = threading.Event()

# clientes conectados: socket -> nome
clientes = {}

# usuários persistidos
usuarios = {}

# leilões ativos
leiloes = {
    "carro": {
        "item": "carro",
        "lance_atual": 4000.0,
        "vencedor": None,
        "tempo": 300,
        "ativo": True
    }
}


def carregar_dados():
    global usuarios
    if os.path.exists(ARQ_DADOS):
        try:
            with open(ARQ_DADOS, "r", encoding="utf-8") as f:
                usuarios = json.load(f)
        except (json.JSONDecodeError, OSError):
            print("[ERRO] Arquivo de dados inválido. Iniciando com base vazia.")
            usuarios = {}
    else:
        usuarios = {}


def salvar_dados():
    try:
        with open(ARQ_DADOS, "w", encoding="utf-8") as f:
            json.dump(usuarios, f, indent=4, ensure_ascii=False)
    except OSError as e:
        print(f"[ERRO] Falha ao salvar dados: {e}")


def enviar(sock, tipo, mensagem):
    try:
        sock.sendall(f"[{tipo}] {mensagem}".encode())
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def broadcast(tipo, mensagem):
    mortos = []
    for sock in list(clientes.keys()):
        ok = enviar(sock, tipo, mensagem)
        if not ok:
            mortos.append(sock)

    for sock in mortos:
        remover_cliente(sock)


def remover_cliente(sock):
    with lock:
        nome = clientes.pop(sock, None)

    if nome:
        print(f"[INFO] Cliente desconectado: {nome}")

    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass

    try:
        sock.close()
    except OSError:
        pass


def saldo_disponivel(nome):
    return usuarios[nome]["saldo"] - usuarios[nome]["bloqueado"]


def listar_leiloes():
    linhas = ["--- LEILÕES EM EXECUÇÃO ---"]
    for nome_item, dados in leiloes.items():
        status = "ATIVO" if dados["ativo"] else "ENCERRADO"
        vencedor = dados["vencedor"] if dados["vencedor"] else "ninguém"
        linhas.append(
            f"{nome_item} | Lance atual: R${dados['lance_atual']:.2f} | "
            f"Tempo: {dados['tempo']}s | Vencedor atual: {vencedor} | {status}"
        )
    return "\n".join(linhas)


def registrar_ou_carregar_usuario(nome):
    if nome not in usuarios:
        usuarios[nome] = {
            "saldo": 5000.0,
            "bloqueado": 0.0,
            "itens": {}
        }
        salvar_dados()
        return True
    return False


def processar_lance(sock, nome_usuario, item, valor):
    with lock:
        if item not in leiloes:
            enviar(sock, "ERRO", f"Item '{item}' não existe.")
            return

        dados = leiloes[item]

        if not dados["ativo"]:
            enviar(sock, "ERRO", f"O leilão de '{item}' já encerrou.")
            return

        try:
            valor = float(valor)
        except ValueError:
            enviar(sock, "ERRO", "Valor de lance inválido.")
            return

        if valor <= dados["lance_atual"]:
            enviar(sock, "ERRO", "Lance precisa ser maior que o atual.")
            return

        if saldo_disponivel(nome_usuario) < valor:
            enviar(sock, "ERRO", "Saldo disponível insuficiente para esse lance.")
            return

        vencedor_antigo = dados["vencedor"]
        valor_antigo = dados["lance_atual"]

        if vencedor_antigo is not None:
            usuarios[vencedor_antigo]["bloqueado"] -= valor_antigo
            if usuarios[vencedor_antigo]["bloqueado"] < 0:
                usuarios[vencedor_antigo]["bloqueado"] = 0.0

        usuarios[nome_usuario]["bloqueado"] += valor
        dados["lance_atual"] = valor
        dados["vencedor"] = nome_usuario
        dados["tempo"] = 30

        salvar_dados()

    enviar(sock, "COMANDO", f"Você executou: :Lance {item} {valor}")
    broadcast("INFO", f"Atualização do leilão:\n{listar_leiloes()}")


def processar_venda(sock, nome_usuario, item):
    with lock:
        if item not in usuarios[nome_usuario]["itens"]:
            enviar(sock, "ERRO", f"Você não possui o item '{item}'.")
            return

        preco_compra = usuarios[nome_usuario]["itens"][item]
        valor_venda = preco_compra * 0.9

        usuarios[nome_usuario]["saldo"] += valor_venda
        del usuarios[nome_usuario]["itens"][item]

        salvar_dados()

    enviar(sock, "COMANDO", f"Você executou: :Vender {item}")
    enviar(sock, "INFO", f"Item '{item}' vendido por R${valor_venda:.2f}.")


def tratar_comandos(sock, nome_usuario):
    while not encerrar_servidor.is_set():
        try:
            dados = sock.recv(1024)

            if not dados:
                print(f"[INFO] Conexão encerrada sem :quit por {nome_usuario}.")
                break

            msg = dados.decode().strip()

            if not msg:
                continue

            if msg.lower() == ":quit":
                enviar(sock, "INFO", "Desconectando...")
                break

            elif msg.lower() == ":saldo":
                with lock:
                    saldo = usuarios[nome_usuario]["saldo"]
                    bloqueado = usuarios[nome_usuario]["bloqueado"]
                    itens = usuarios[nome_usuario]["itens"].copy()

                texto_itens = ", ".join(
                    [f"{k}(R${v:.2f})" for k, v in itens.items()]
                ) if itens else "nenhum"

                enviar(
                    sock,
                    "INFO",
                    f"Saldo: R${saldo:.2f} | Bloqueado: R${bloqueado:.2f} | "
                    f"Disponível: R${saldo - bloqueado:.2f} | Itens: {texto_itens}"
                )

            elif msg.lower() == ":leiloes":
                enviar(sock, "INFO", listar_leiloes())

            elif msg.lower().startswith(":lance "):
                partes = msg.split()
                if len(partes) != 3:
                    enviar(sock, "ERRO", "Use: :Lance <item> <valor>")
                    continue
                _, item, valor = partes
                processar_lance(sock, nome_usuario, item, valor)

            elif msg.lower().startswith(":vender "):
                partes = msg.split(maxsplit=1)
                if len(partes) != 2:
                    enviar(sock, "ERRO", "Use: :Vender <item>")
                    continue
                _, item = partes
                processar_venda(sock, nome_usuario, item)

            else:
                enviar(sock, "ERRO", "Comando inválido.")

        except ConnectionResetError:
            print(f"[INFO] Cliente {nome_usuario} desconectou abruptamente.")
            break
        except OSError:
            break
        except Exception as e:
            print(f"[ERRO] Falha ao tratar comandos de {nome_usuario}: {e}")
            break

    remover_cliente(sock)


def thread_leiloes():
    while not encerrar_servidor.is_set():
        time.sleep(1)

        encerrados = []

        with lock:
            for item, dados in leiloes.items():
                if dados["ativo"]:
                    dados["tempo"] -= 1

                    if dados["tempo"] <= 0:
                        dados["ativo"] = False
                        vencedor = dados["vencedor"]
                        valor_final = dados["lance_atual"]

                        if vencedor is not None:
                            usuarios[vencedor]["bloqueado"] -= valor_final
                            if usuarios[vencedor]["bloqueado"] < 0:
                                usuarios[vencedor]["bloqueado"] = 0.0

                            usuarios[vencedor]["saldo"] -= valor_final
                            usuarios[vencedor]["itens"][item] = valor_final

                        encerrados.append((item, vencedor, valor_final))

            if encerrados:
                salvar_dados()

        for item, vencedor, valor_final in encerrados:
            if vencedor:
                broadcast(
                    "ALERTA",
                    f"Leilão encerrado! '{item}' vendido para {vencedor} por R${valor_final:.2f}"
                )
            else:
                broadcast(
                    "ALERTA",
                    f"Leilão encerrado! '{item}' não recebeu lances."
                )


def encerrar_todos_clientes():
    for sock in list(clientes.keys()):
        enviar(sock, "ALERTA", "Servidor será encerrado.")
        remover_cliente(sock)


def aceitar_clientes(limite_conexoes):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    server.settimeout(1)

    print(f"[INFO] Servidor ouvindo em {HOST}:{PORT} | limite = {limite_conexoes}")

    try:
        while not encerrar_servidor.is_set():
            try:
                sock, endereco = server.accept()
            except socket.timeout:
                continue
            except OSError:
                if encerrar_servidor.is_set():
                    break
                raise

            with lock:
                if len(clientes) >= limite_conexoes:
                    enviar(sock, "ERRO", "Servidor lotado. Tente novamente mais tarde.")
                    try:
                        sock.close()
                    except OSError:
                        pass
                    continue

            try:
                hora = datetime.now().strftime("%H:%M:%S")
                enviar(sock, "INFO", f"{hora}: CONECTADO!!")
                enviar(sock, "INFO", listar_leiloes())
                enviar(sock, "INFO", "Digite seu nome de usuário:")

                sock.settimeout(20)
                nome = sock.recv(1024).decode().strip()
                sock.settimeout(None)

                if not nome:
                    enviar(sock, "ERRO", "Nome inválido.")
                    sock.close()
                    continue

                with lock:
                    novo = registrar_ou_carregar_usuario(nome)
                    clientes[sock] = nome
                    saldo = usuarios[nome]["saldo"]
                    itens = usuarios[nome]["itens"].copy()

                print(f"[INFO] Cliente conectado: {nome} ({endereco[0]}:{endereco[1]})")

                if novo:
                    enviar(sock, "INFO", f"Usuário novo '{nome}' criado com 5000 créditos.")
                else:
                    enviar(sock, "INFO", f"Bem-vindo de volta, {nome}.")

                itens_txt = ", ".join(itens.keys()) if itens else "nenhum"
                enviar(sock, "INFO", f"Saldo atual: R${saldo:.2f} | Itens: {itens_txt}")

                t = threading.Thread(target=tratar_comandos, args=(sock, nome), daemon=True)
                t.start()

            except socket.timeout:
                enviar(sock, "ERRO", "Tempo esgotado para informar o nome de usuário.")
                try:
                    sock.close()
                except OSError:
                    pass
            except Exception as e:
                print(f"[ERRO] Falha ao aceitar cliente: {e}")
                try:
                    sock.close()
                except OSError:
                    pass
    finally:
        salvar_dados()
        try:
            server.close()
        except OSError:
            pass


def main():
    carregar_dados()

    if len(sys.argv) != 2:
        print("Uso: py servidor.py <limite_conexoes>")
        return

    try:
        limite = int(sys.argv[1])
        if limite <= 0:
            print("O limite de conexões deve ser maior que zero.")
            return
    except ValueError:
        print("O limite de conexões deve ser um número inteiro.")
        return

    threading.Thread(target=thread_leiloes, daemon=True).start()

    try:
        aceitar_clientes(limite)
    except KeyboardInterrupt:
        print("\n[INFO] Encerrando servidor com segurança...")
    finally:
        encerrar_servidor.set()
        salvar_dados()
        encerrar_todos_clientes()
        print("[INFO] Dados salvos. Servidor encerrado.")


if __name__ == "__main__":
    main()