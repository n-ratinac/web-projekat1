import asyncio
import socket
import websockets
import json
import datetime
import math
import random

WORLD = 4000
FOOD_COUNT = 70
FOOD_MASS = 1
BOT_COUNT = 8
BOT_SPEED = 0.3
BOT_NAMES = ["Sava", "Sibin", "Djani", "Mili", "Dzoni", "Boris", "Vuk", "Lazar", "Pera", "Mika", "Zika", "Paprika", "JakaSpika"]

# Svi konektovani igraci: { websocket: { id, ime, hue, alive, cells[], target_x, target_y } }
connected_clients = {}

# Botovi: { bot_id: { id, ime, hue, alive, cells[], target_x, target_y } }
bots = {}

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
    global food_list
    food_list = [spawn_food() for _ in range(FOOD_COUNT)]
    log(f"Inicijalizovano {FOOD_COUNT} food pellet-a.")

def random_target():
    return random.uniform(200, WORLD - 200), random.uniform(200, WORLD - 200)

def init_bots():
    used_names = []
    for i in range(BOT_COUNT):
        bot_id = f"bot_{i}"
        available = [n for n in BOT_NAMES if n not in used_names]
        name = random.choice(available if available else BOT_NAMES)
        used_names.append(name)
        x, y = random.uniform(100, WORLD - 100), random.uniform(100, WORLD - 100)
        tx, ty = random_target()
        mass = 50
        bots[bot_id] = {
            "id": bot_id,
            "ime": name,
            "hue": random.randint(0, 360),
            "alive": True,
            "cells": [{"x": x, "y": y, "mass": mass, "r": mass_to_r(mass)}],
            "target_x": tx,
            "target_y": ty
        }
    log(f"Inicijalizovano {BOT_COUNT} botova.")

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

def move_entity(entity, speed_mult=1.0):
    for cell in entity["cells"]:
        dx = entity["target_x"] - cell["x"]
        dy = entity["target_y"] - cell["y"]
        norm_x, norm_y = normalize_direction(dx, dy)
        speed = (800 / math.sqrt(cell["mass"])) * speed_mult
        cell["x"] = max(0, min(WORLD, cell["x"] + norm_x * speed))
        cell["y"] = max(0, min(WORLD, cell["y"] + norm_y * speed))

def check_entity_collisions(entities):
    """
    Predator može pojesti prey ćeliju ako:
      mass_pred > mass_prey * 1.15  i  dist < r_pred - r_prey * 0.3
    """
    for i in range(len(entities)):
        for j in range(len(entities)):
            if i == j:
                continue
            predator = entities[i]
            prey = entities[j]
            if not predator["alive"] or not prey["alive"]:
                continue

            eaten = []
            for pred_cell in predator["cells"]:
                for prey_cell in prey["cells"]:
                    if prey_cell in eaten:
                        continue
                    dx = pred_cell["x"] - prey_cell["x"]
                    dy = pred_cell["y"] - prey_cell["y"]
                    dist = math.sqrt(dx**2 + dy**2)
                    if (pred_cell["mass"] > prey_cell["mass"] * 1.15
                            and dist < pred_cell["r"] - prey_cell["r"] * 0.3):
                        eaten.append(prey_cell)
                        pred_cell["mass"] += prey_cell["mass"]
                        pred_cell["r"] = mass_to_r(pred_cell["mass"])

            for cell in eaten:
                prey["cells"].remove(cell)
                log(f"{predator['ime']} pojeo ćeliju od {prey['ime']}")

            if not prey["cells"]:
                prey["alive"] = False
                log(f"{prey['ime']} je mrtav (pojeo: {predator['ime']})")

async def game_loop():
    while True:
        # Pomeri igrače
        for player in list(connected_clients.values()):
            if not player["alive"]:
                continue
            move_entity(player)
            check_food_collisions(player)

        # Pomeri botove
        for bot in bots.values():
            cell = bot["cells"][0]
            dx = bot["target_x"] - cell["x"]
            dy = bot["target_y"] - cell["y"]
            dist = math.sqrt(dx**2 + dy**2)

            # Novi cilj kad stigne ili nasumično (2% šansa po tiku)
            if dist < 60 or random.random() < 0.02:
                bot["target_x"], bot["target_y"] = random_target()

            move_entity(bot, BOT_SPEED)
            check_food_collisions(bot)

        # Proveri jedenje između svih entiteta
        all_entities = (
            [p for p in connected_clients.values()] +
            [b for b in bots.values()]
        )
        check_entity_collisions(all_entities)

        if connected_clients:
            lista_igraca = list(connected_clients.values()) + list(bots.values())
            poruka = json.dumps({
                "type": "game_state",
                "igraci": lista_igraca,
                "hrana": food_list
            })

            for ws in list(connected_clients.keys()):
                try:
                    await ws.send(poruka)
                except websockets.exceptions.ConnectionClosed:
                    pass

        await asyncio.sleep(1 / 20)


async def handle_client(websocket):
    client_ip = websocket.remote_address[0]
    player_id = str(id(websocket))

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

    try:
        async for message in websocket:
            try:
                data = json.loads(message)

                if data["type"] == "join":
                    connected_clients[websocket]["ime"] = data.get("ime", "Igrac")
                    log(f"Igrac se pridružio: {connected_clients[websocket]['ime']}")
                    await websocket.send(json.dumps({
                        "type": "welcome",
                        "id": player_id
                    }))

                elif data["type"] == "move":
                    connected_clients[websocket]["target_x"] = data["x"]
                    connected_clients[websocket]["target_y"] = data["y"]

            except json.JSONDecodeError:
                log(f"Nevalidan JSON od {client_ip}")

    except websockets.exceptions.ConnectionClosed:
        log(f"[{client_ip}] Klijent se diskonektovao")
    finally:
        connected_clients.pop(websocket, None)
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
    init_bots()
    log("WebSocket server startovan na ws://0.0.0.0:8765")
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        asyncio.create_task(game_loop())
        await asyncio.Future()

asyncio.run(main())
