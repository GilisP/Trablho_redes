import socket
import threading
import time
from datetime import datetime

HOST = "127.0.0.1"
PORT = 65432

item = 'carro'
lance_atual = 50000
tempo = 30
leilao = True

def atualizar(conexao):
    global lance_atual, tempo, leilao, item
    while leilao:
        pego = conexao.recv(1024).decode()
        if not pego:
            leilao = False
            break
        elif(pego==":item"):
            desc = f'\nITEM: {item}\nLance Atual: R${lance_atual}'
            conexao.sendall(desc.encode())
        elif(pego==":tempo"):
            tempo_rest = f'\nFaltam {tempo} segundos para o fim do Leilão!!!'
            conexao.sendall(tempo_rest.encode())
        elif(pego.isdigit()):
            novo_lance = float(pego)
            if (novo_lance > lance_atual):
                lance_atual = novo_lance
                tempo = 30
                conexao.sendall("\nLance Aceito!\n".encode())
            else:
                conexao.sendall("\nLance Recusado! Valor lançado abaixo do atual\n".encode())

def timer(conexao):
    global tempo, leilao
    while tempo>0:
        time.sleep(1)
        tempo -= 1

    leilao = False
    conexao.sendall(f"Leilão Encerrado! Item vendido no valor de R${lance_atual}".encode())
        
server = socket.socket()
server.bind((HOST,PORT))

server.listen()
print("AGUARDANDO CONEXÃO...")

conexao, endereco = server.accept()
print(f"Conectado pelo: {endereco}")

hora = datetime.now().strftime("%H:%M:%S")
msg = f'{hora} - CONECTADO!\n\n------INFORMAÇÕES DO LEILÃO------\nItem a venda: {item}\nLance Inicial: R${lance_atual}'

conexao.sendall(msg.encode())

t1 = threading.Thread(target= atualizar, args= (conexao,))
t2 = threading.Thread(target= timer, args= (conexao,))

t1.start()
t2.start()