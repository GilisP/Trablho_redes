import socket
import threading

HOST = "127.0.0.1"
PORT = 65432


def receber_msg(sock):
    while True:
        try:
            msg = sock.recv(1024)
            if not msg:
                print("\nConexão encerrada pelo servidor.")
                break
            print("\n" + msg.decode())
        except:
            print("\nErro na conexão com o servidor.")
            break


def enviar_msg(sock):
    while True:
        try:
            msg = input("\nDigite um comando: ")
            sock.sendall(msg.encode())

            if msg.lower() == ":quit":
                break
        except:
            break


def main():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))

    t1 = threading.Thread(target=enviar_msg, args=(client,))
    t2 = threading.Thread(target=receber_msg, args=(client,))

    t1.start()
    t2.start()

    t1.join()
    try:
        client.close()
    except:
        pass


if __name__ == "__main__":
    main()