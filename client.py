import socket
import threading

HOST = "127.0.0.1"
PORT = 65432

encerrar = threading.Event()


def receber_msg(sock):
    while not encerrar.is_set():
        try:
            msg = sock.recv(1024)

            if not msg:
                print("\n[INFO] Conexão encerrada pelo servidor.")
                encerrar.set()
                break

            print("\n" + msg.decode())

        except ConnectionResetError:
            print("\n[ERRO] A conexão foi resetada pelo servidor.")
            encerrar.set()
            break
        except OSError:
            if not encerrar.is_set():
                print("\n[ERRO] Socket do cliente foi fechado.")
                encerrar.set()
            break
        except Exception as e:
            print(f"\n[ERRO] Falha ao receber mensagem: {e}")
            encerrar.set()
            break


def enviar_msg(sock):
    while not encerrar.is_set():
        try:
            msg = input("\nDigite um comando: ").strip()

            if not msg:
                continue

            sock.sendall(msg.encode())

            if msg.lower() == ":quit":
                print("[INFO] Encerrando cliente...")
                encerrar.set()
                break

        except EOFError:
            print("\n[INFO] Entrada encerrada.")
            encerrar.set()
            break
        except BrokenPipeError:
            print("\n[ERRO] Não foi possível enviar: servidor desconectado.")
            encerrar.set()
            break
        except OSError:
            if not encerrar.is_set():
                print("\n[ERRO] Socket fechado durante envio.")
                encerrar.set()
            break
        except Exception as e:
            print(f"\n[ERRO] Falha ao enviar mensagem: {e}")
            encerrar.set()
            break


def fechar_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass

    try:
        sock.close()
    except OSError:
        pass


def main():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client.connect((HOST, PORT))
        print(f"[INFO] Conectado ao servidor em {HOST}:{PORT}")
    except ConnectionRefusedError:
        print("[ERRO] Não foi possível conectar: servidor indisponível ou desligado.")
        return
    except OSError as e:
        print(f"[ERRO] Falha na conexão: {e}")
        return

    t_envio = threading.Thread(target=enviar_msg, args=(client,), daemon=True)
    t_receb = threading.Thread(target=receber_msg, args=(client,), daemon=True)

    t_envio.start()
    t_receb.start()

    try:
        while t_envio.is_alive() or t_receb.is_alive():
            t_envio.join(timeout=0.2)
            t_receb.join(timeout=0.2)
    except KeyboardInterrupt:
        print("\n[INFO] Cliente interrompido pelo usuário.")
        encerrar.set()
    finally:
        encerrar.set()
        fechar_socket(client)
        print("[INFO] Cliente encerrado.")


if __name__ == "__main__":
    main()
