import asyncio
import websockets
import datetime

# Čuvaćemo sve konektovane klijente ovde
connected_clients = {}

async def handle_client(websocket):
    # Uzimamo IP adresu klijenta
    client_ip = websocket.remote_address[0]
    connect_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"[{connect_time}] Nova konekcija od: {client_ip}")
    
    try:
        async for message in websocket:
            print(f"[{client_ip}] Primljena poruka: {message}")
            
            # Odgovaramo klijentu
            await websocket.send(f"Server primio: {message}")
    
    except websockets.exceptions.ConnectionClosed:
        print(f"[{client_ip}] Klijent se diskonektovao")

async def main():
    print("WebSocket server startovan na ws://localhost:8765")
    async with websockets.serve(handle_client, "localhost", 8765):
        await asyncio.Future()  # drži server u radu zauvek

asyncio.run(main())