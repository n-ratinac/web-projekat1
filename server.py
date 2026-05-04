import asyncio
import websockets
import json
import datetime

# Svi konektovani igraci: { websocket: { id, x, y, ime } }
connected_clients = {}

def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

async def handle_client(websocket):
    client_ip = websocket.remote_address[0]
    player_id = str(id(websocket))
    connect_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log(f"Nova konekcija od: {client_ip} (id: {player_id})")

    # Dodaj igraca sa pocetnom pozicijom
    connected_clients[websocket] = {
        "id": player_id,
        "x": 400,
        "y": 300,
        "ime": "Igrac"
    }

    async def primaj():
        try:
            async for message in websocket:
                log(f"[{client_ip}] Primljena poruka: {message}")

                data = json.loads(message)

                if data["type"] == "join":
                    connected_clients[websocket]["ime"] = data.get("ime", "Igrac")
                    log(f"Igrac se pridružio: {connected_clients[websocket]['ime']}")

                elif data["type"] == "move":
                    connected_clients[websocket]["x"] = data["x"]
                    connected_clients[websocket]["y"] = data["y"]

        except websockets.exceptions.ConnectionClosed:
            log(f"[{client_ip}] Klijent se diskonektovao")
        except json.JSONDecodeError:
            log(f"Nevalidan JSON od {client_ip}")

    async def salji_periodicno():
        try:
            while True:
                lista = list(connected_clients.values())

                poruka = json.dumps({
                    "type": "game_state",
                    "igraci": lista
                })

                await websocket.send(poruka)
                await asyncio.sleep(1 / 20)  # 20 FPS

        except websockets.exceptions.ConnectionClosed:
            pass

    try:
        await asyncio.gather(primaj(), salji_periodicno())
    finally:
        del connected_clients[websocket]
        log(f"Igrac {player_id} uklonjen. Online: {len(connected_clients)}")

async def main():
    log("WebSocket server startovan na ws://10.0.5.14:8765")
    async with websockets.serve(handle_client, "10.0.5.14", 8765):
        await asyncio.Future()

asyncio.run(main())