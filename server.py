import asyncio
import socket
import websockets
import json
import datetime
import math

# Svi konektovani igraci: { websocket: { id, x, y, ime, target_x, target_y } }
connected_clients = {}

def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

def normalize_direction(dx, dy):
    """Normaliza pravac i vraća jedinični vektor. Ako je dužina 0, vraća (0, 0)."""
    magnitude = math.sqrt(dx**2 + dy**2)
    if magnitude == 0:
        return 0, 0
    return dx / magnitude, dy / magnitude

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
        "ime": "Igrac",
        "target_x": 400,
        "target_y": 300
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
                    # Čuva ciljnu poziciju miša
                    connected_clients[websocket]["target_x"] = data["x"]
                    connected_clients[websocket]["target_y"] = data["y"]

        except websockets.exceptions.ConnectionClosed:
            log(f"[{client_ip}] Klijent se diskonektovao")
        except json.JSONDecodeError:
            log(f"Nevalidan JSON od {client_ip}")

    async def salji_periodicno():
        try:
            while True:
                # Pomeri igrača 1 jedinicu po frame-u prema ciljnoj poziciji
                player = connected_clients[websocket]
                dx = player["target_x"] - player["x"]
                dy = player["target_y"] - player["y"]
                norm_x, norm_y = normalize_direction(dx, dy)
                player["x"] += norm_x
                player["y"] += norm_y

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


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.0.5.101", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

async def main():
    local_ip = get_local_ip()
    log(f"WebSocket server startovan na ws://{local_ip}:8765 (dostupno u lokalnoj mreži)")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()

asyncio.run(main())