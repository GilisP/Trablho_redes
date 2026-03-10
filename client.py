import socket
import threading
def receber_msg(user):
    while True:
        msg = user.recv(1024)
        msg = msg.decode()
        if (msg==""):
            break
        print(msg)

def enviar_msg(user):
    while True:
        resp = input("\nDigite um lance ou um comando: ")
        if(resp[0]==':'):
            if(resp==':quit'):
                user.close()
                break
        user.sendall(resp.encode())

HOST = "127.0.0.1"
PORT = 65432

client = socket.socket()

client.connect((HOST, PORT))
print(f"Conectado ao servidor!")

mensagem = client.recv(1024)
mensagem = mensagem.decode()
print(mensagem)

t1 = threading.Thread(target= enviar_msg, args = (client,))
t2 = threading.Thread(target= receber_msg, args = (client,))

t1.start()
t2.start()