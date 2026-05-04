import asyncio
import socket
import websockets
import json
import datetime
import math
import random

WORLD = 4000
FOOD_COUNT = 600
FOOD_MASS = 1

# Svi konektovani igraci: { websocket: { id, ime, hue, alive, cells[], target_x, target_y } }
connected_clients = {}

# Lista hrane: [ {id, x, y, mass, hue} ]
food_list = []
food_id_counter = 0

def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

def mass_to_r(mass):
    """Ista formula kao u _index.html: sqrt(mass / PI) * 4"""
    return math.sqrt(mass / math.pi) * 4

def normalize_direction(dx, dy):
    magnitude = math.sqrt(dx**2 + dy**2)
    if magnitude == 0:
        return 0, 0
    return dx / magnitude, dy / magnitude

def spawn_food():
    """Kreira jedan novi food pellet na nasumičnoj poziciji."""
    global food_id_counter
    food_id_counter += 1
    return {
        "id": food_id_counter,
        "x": random.uniform(0, WORLD),
        "y": random.uniform(0, WORLD),
        "mass": FOOD_MASS,
        "hue": random.randint(0, 360)
    }

def init_food():
    """Inicijalizuje 600 food pellet-a pri startu servera."""
    global food_list
    food_list = [spawn_food() for _ in range(FOOD_COUNT)]
    log(f"Inicijalizovano {FOOD_COUNT} food pellet-a.")

def check_food_collisions(player):
    """
    Proverava da li je neka ćelija igrača pojela food pellet.
    Ako jeste: povećava masu ćelije, uklanja pellet i spawna novi.
    """
    eaten = []
    for cell in player["cells"]:
        for pellet in food_list:
            dx = cell["x"] - pellet["x"]
            dy = cell["y"] - pellet["y"]
            dist = math.sqrt(dx**2 + dy**2)
            if dist < cell["r"]:
                eaten.append(pellet)
                cell["mass"] += pellet["mass"]
                cell["r"] = mass_to_r(cell["mass"])

    for pellet in eaten:
        food_list.remove(pellet)
        food_list.append(spawn_food())

async def handle_client(websocket):
    client_ip = websocket.remote_address[0]
    player_id = str(id(websocket))
    connect_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log(f"Nova konekcija od: {client_ip} (id: {player_id})")

    start_x = random.uniform(100, WORLD - 100)
    start_y = random.uniform(100, WORLD - 100)
    start_mass = 50

    connected_clients[websocket] = {
        "id": player_id,
        "ime": "Igrac",
        "hue": random.randint(0, 360),
        "alive": True,
        "cells": [
            {
                "x": start_x,
                "y": start_y,
                "mass": start_mass,
                "r": mass_to_r(start_mass)
            }
        ],
        "target_x": start_x,
        "target_y": start_y
    }

    async def primaj():
        try:
            async for message in websocket:
                data = json.loads(message)

                if data["type"] == "join":
                    connected_clients[websocket]["ime"] = data.get("ime", "Igrac")
                    log(f"Igrac se pridružio: {connected_clients[websocket]['ime']}")

                    # #1 — welcome poruka sa dodeljivanjem ID-a
                    await websocket.send(json.dumps({
                        "type": "welcome",
                        "id": player_id
                    }))

                elif data["type"] == "move":
                    connected_clients[websocket]["target_x"] = data["x"]
                    connected_clients[websocket]["target_y"] = data["y"]

        except websockets.exceptions.ConnectionClosed:
            log(f"[{client_ip}] Klijent se diskonektovao")
        except json.JSONDecodeError:
            log(f"Nevalidan JSON od {client_ip}")

    async def salji_periodicno():
        try:
            while True:
                player = connected_clients[websocket]

                # Pomeri svaku ćeliju prema target poziciji
                for cell in player["cells"]:
                    dx = player["target_x"] - cell["x"]
                    dy = player["target_y"] - cell["y"]
                    norm_x, norm_y = normalize_direction(dx, dy)

                    # Brzina zavisi od mase (kao u singleplayer)
                    speed = 800 / math.sqrt(cell["mass"])
                    cell["x"] += norm_x * speed
                    cell["y"] += norm_y * speed

                    # Zadrži unutar mape
                    cell["x"] = max(0, min(WORLD, cell["x"]))
                    cell["y"] = max(0, min(WORLD, cell["y"]))

                # #4 — kolizija sa hranom
                check_food_collisions(player)

                # Pripremi listu igrača za slanje (bez websocket ključa)
                lista_igraca = list(connected_clients.values())

                poruka = json.dumps({
                    "type": "game_state",
                    "igraci": lista_igraca,
                    "hrana": food_list
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
    init_food()
    log("WebSocket server startovan na ws://10.0.5.14:8765")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()

asyncio.run(main())
