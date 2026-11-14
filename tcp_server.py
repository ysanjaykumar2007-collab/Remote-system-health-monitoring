import socket
import threading

HOST = '0.0.0.0'
PORT = 6000


def handle_client(conn, address):
    print(f"TCP client connected: {address}")

    try:
        data = conn.recv(4096)

        if data:
            message = data.decode().strip()
            print(f"TCP request: {message}")

            response = (
                "Health Monitoring TCP Server\n"
                "Status: OK\n"
                "Use UDP port 5000 for periodic health reports.\n"
            )

            conn.sendall(response.encode())

    except Exception as error:
        print(f"TCP client error: {error}")

    finally:
        conn.close()
        print(f"TCP client disconnected: {address}")


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(10)

print("TCP Health Service started")
print(f"Listening on TCP port {PORT}...")

while True:
    conn, address = server.accept()

    thread = threading.Thread(
        target=handle_client,
        args=(conn, address),
        daemon=True
    )

    thread.start()
