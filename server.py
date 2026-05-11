import asyncio
import websockets
import json
import datetime
import math
import random
import time

# --- KONSTANTE ---
WORLD = 4000
FOOD_COUNT = 600
FOOD_MASS = 4.5
TICK_RATE = 1 / 30
MERGE_DELAY = 15  # Sekunde pre nego što ćelije mogu da se spoje (Fix #3)

connected_clients = {}
food_list = []
virus_list = []
food_id_counter = 0

def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

def mass_to_r(mass):
    return math.sqrt(mass / math.pi) * 4

def normalize_direction(dx, dy):
    magnitude = math.sqrt(dx**2 + dy**2)
    if magnitude < 5: 
        return 0, 0
    return dx / magnitude, dy / magnitude

# --- HRANA ---
def spawn_food():
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
    log(f"Inicijalizovano {FOOD_COUNT} pellet-a hrane.")

def check_food_collisions(player):
    global food_list
    eaten = []
    
    for cell in player["cells"]:
        for pellet in food_list:
            # Preskačemo hranu ako ju je već pojela neka druga tvoja ćelija (kada si splitovan)
            if pellet in eaten:
                continue
                
            dx = cell["x"] - pellet["x"]
            dy = cell["y"] - pellet["y"]
            dist = math.sqrt(dx**2 + dy**2)
            
            # 1. Uzimamo poluprečnik hrane (15 za izbačenu masu, 5 za obične mrvice)
            food_r = pellet.get("r", 5)
            
            # 2. Sudar se dešava čim se ivice dodirnu
            if dist < cell["r"] + food_r + 15:
                eaten.append(pellet)
                # 3. Dajemo pravu masu 
                cell["mass"] += pellet.get("mass", FOOD_MASS)
                cell["r"] = mass_to_r(cell["mass"])
                log(f"Pojedena hrana! {player['ime']} sada ima masu: {round(cell['mass'], 1)}")

    # 4. Brisanje pojedene hrane i stvaranje nove
    for pellet in eaten:
        if pellet in food_list:
            food_list.remove(pellet)
            
            # Stvaramo novu mrvicu SAMO ako nismo upravo pojeli izbačenu masu
            if not pellet.get("is_ejected"):
                food_list.append(spawn_food())

# --- LOGIKA SPAJANJA (Fix #3) ---
def check_internal_merges(player):
    """Logika koja spaja razdvojene ćelije istog igrača nakon MERGE_DELAY sekundi."""
    if len(player["cells"]) < 2: return
    
    now = time.time() # Koristimo sekunde umesto datetime
    i = 0
    while i < len(player["cells"]):
        j = i + 1
        while j < len(player["cells"]):
            c1 = player["cells"][i]
            c2 = player["cells"][j]
            
            # Provera da li su obe ćelije spremne za spajanje (koristeći obične brojeve)
            if now > c1.get("merge_at", 0) and now > c2.get("merge_at", 0):
                dx = c1["x"] - c2["x"]
                dy = c1["y"] - c2["y"]
                dist = math.sqrt(dx**2 + dy**2)
                
                # Ako se dodiruju dovoljno blizu, spoji ih
                if dist < (c1["r"] + c2["r"]) * 0.8:
                    c1["mass"] += c2["mass"]
                    c1["r"] = mass_to_r(c1["mass"])
                    player["cells"].pop(j)
                    log(f"Ćelije igrača {player['ime']} su se ponovo spojile!")
                    continue
            j += 1
        i += 1
def resolve_self_collisions(player):
    """Sprečava da ćelije istog igrača prelaze jedna preko druge dok se ne spoje."""
    cells = player["cells"]
    now = time.time()
    
    # Proveravamo svaki par tvojih ćelija
    for i in range(len(cells)):
        for j in range(i + 1, len(cells)):
            c1 = cells[i]
            c2 = cells[j]
            
            # Ako su OBA tajmera istekla, pusti ih da se preklapaju i spoje!
            if now > c1.get("merge_at", 0) and now > c2.get("merge_at", 0):
                continue
                
            dx = c1["x"] - c2["x"]
            dy = c1["y"] - c2["y"]
            dist = math.sqrt(dx**2 + dy**2)
            min_dist = c1["r"] + c2["r"] # Minimalna udaljenost (zbir poluprečnika)
            
            # Ako su preblizu (preklapaju se)
            if dist < min_dist:
                if dist == 0: # Ako su bukvalno u istom pikselu (da izbegnemo deljenje sa nulom)
                    dx, dy = random.uniform(-1, 1), random.uniform(-1, 1)
                    dist = math.sqrt(dx**2 + dy**2)
                    
                overlap = min_dist - dist
                nx = dx / dist
                ny = dy / dist
                
                # Odgurni prvu ćeliju na jednu stranu, a drugu na suprotnu
                c1["x"] += nx * (overlap / 2)
                c1["y"] += ny * (overlap / 2)
                c2["x"] -= nx * (overlap / 2)
                c2["y"] -= ny * (overlap / 2)

# --- KOLIZIJA IZMEĐU IGRAČA ---
async def check_player_collisions():
    svi_klijenti = list(connected_clients.keys())
    for ws_predator in svi_klijenti:
        predator = connected_clients[ws_predator]
        if not predator["alive"]: continue
        for ws_prey in svi_klijenti:
            prey = connected_clients[ws_prey]
            if not prey["alive"] or predator["id"] == prey["id"]: continue
            for p_cell in predator["cells"]:
                for prey_cell in prey["cells"][:]:
                    dx = p_cell["x"] - prey_cell["x"]
                    dy = p_cell["y"] - prey_cell["y"]
                    dist = math.sqrt(dx**2 + dy**2)
                    if p_cell["mass"] > prey_cell["mass"] * 1.15:
                        if dist < p_cell["r"] - prey_cell["r"] * 0.3:
                            log(f"{predator['ime']} je pojeo ćeliju igrača {prey['ime']}")
                            p_cell["mass"] += prey_cell["mass"]
                            p_cell["r"] = mass_to_r(p_cell["mass"])
                            prey["cells"].remove(prey_cell)
                            if len(prey["cells"]) == 0:
                                prey["alive"] = False
                                log(f"Igrač {prey['ime']} je pojeden!")
                                try:
                                    await ws_prey.send(json.dumps({"type": "dead", "killer_name": predator["ime"]}))
                                except: pass

def split_player(player):
    if len(player["cells"]) >= 16: return 
    new_cells = []
    # Postavljamo vreme spajanja kao običan broj (timestamp)
    merge_ready_time = time.time() + MERGE_DELAY

    for cell in player["cells"]:
        if cell["mass"] >= 72: 
            half_mass = cell["mass"] / 2
            cell["mass"] = half_mass
            cell["r"] = mass_to_r(half_mass)
            cell["merge_at"] = merge_ready_time 

            dx = player["target_x"] - cell["x"]
            dy = player["target_y"] - cell["y"]
            nx, ny = normalize_direction(dx, dy)

            new_cells.append({
                "x": cell["x"] + nx * cell["r"] * 2.5,
                "y": cell["y"] + ny * cell["r"] * 2.5,
                "mass": half_mass,
                "r": mass_to_r(half_mass),
                "hue": player["hue"],
                "merge_at": merge_ready_time 
            })
            log(f"Split! Igrac {player['ime']} se podelio na {half_mass} mase.")
    player["cells"].extend(new_cells)

def eject_mass(player):
    global food_list
    for cell in player["cells"]:
        if cell["mass"] > 35:
            cell["mass"] -= 18
            cell["r"] = mass_to_r(cell["mass"])
            dx, dy = player["target_x"] - cell["x"], player["target_y"] - cell["y"]
            nx, ny = normalize_direction(dx, dy)
            # POVEĆANA UDALJENOST na 200 (još preko 50% više nego pre)
            food_list.append({
                "id": random.randint(100000, 999999),
                "x": cell["x"] + nx * (cell["r"] + 150), # Smanjeno sa 200 da se izbegne duh-efekat
                "y": cell["y"] + ny * (cell["r"] + 150),
                "mass": 15, 
                "r": 15, # NOVO: Server sada zna da je ova hrana fizički veća!
                "hue": player["hue"],
                "is_ejected": True,
                "source_x": cell["x"],      
                "source_y": cell["y"]       
            })
            log(f"Masa izbačena daleko za igrača {player['ime']}.")
            break

async def handle_client(websocket):
    client_ip = websocket.remote_address[0]
    player_id = str(id(websocket))
    log(f"Nova konekcija: {client_ip} (ID: {player_id})")

    start_x = random.uniform(100, WORLD - 100)
    start_y = random.uniform(100, WORLD - 100)
    
    connected_clients[websocket] = {
        "id": player_id,
        "ime": "Gost",
        "hue": random.randint(0, 360),
        "alive": True,
        "cells": [{"x": start_x, "y": start_y, "mass": 50, "r": mass_to_r(50)}],
        "target_x": start_x,
        "target_y": start_y
    }

    async def primaj_poruke():
        try:
            async for message in websocket:
                data = json.loads(message)
                player = connected_clients[websocket]
                if data["type"] == "join":
                    player["ime"] = data.get("ime", "Igrac")
                    log(f"Igrac '{player['ime']}' se pridružio.")
                    await websocket.send(json.dumps({"type": "welcome", "id": player_id}))
                elif data["type"] == "move":
                    player["target_x"], player["target_y"] = data["x"], data["y"]
                elif data["type"] == "split":
                    split_player(player)
                elif data["type"] == "eject":
                    eject_mass(player)
                elif data["type"] == "respawn":
                    # Resetujemo status igrača na početne vrednosti
                    start_x = random.uniform(100, WORLD - 100)
                    start_y = random.uniform(100, WORLD - 100)
                    player["alive"] = True
                    player["target_x"] = start_x
                    player["target_y"] = start_y
                    player["cells"] = [{
                        "x": start_x,
                        "y": start_y,
                        "mass": 50,
                        "r": mass_to_r(50)
                    }]
                    log(f"Igrač '{player['ime']}' se vratio u igru (Respawn).")
        except: pass

    async def game_loop():
        try:
            while True:
                player = connected_clients[websocket]
                if player["alive"]:
                    # Pomeranje
                    for cell in player["cells"]:
                        dx, dy = player["target_x"] - cell["x"], player["target_y"] - cell["y"]
                        nx, ny = normalize_direction(dx, dy)
                        speed = 200 / math.sqrt(cell["mass"])
                        cell["x"] = max(0, min(WORLD, cell["x"] + nx * speed))
                        cell["y"] = max(0, min(WORLD, cell["y"] + ny * speed))

                    resolve_self_collisions(player)    
                    check_food_collisions(player)
                    check_internal_merges(player) # Aktivacija Fix #3
                    
                    # Virusi
                    for cell in player["cells"][:]:
                        for virus in virus_list:
                            dist = math.sqrt((cell["x"]-virus["x"])**2 + (cell["y"]-virus["y"])**2)
                            if cell["mass"] > 133 and dist < cell["r"] + virus["r"] * 0.2:
                                log(f"VIRUS! Igrač {player['ime']} se raspao.")
                                split_player(player)

                    await check_player_collisions()

                lista_igraca = [p for p in connected_clients.values() if p["alive"]]
                state_msg = json.dumps({
                    "type": "game_state",
                    "igraci": lista_igraca,
                    "hrana": food_list,
                    "virusi": virus_list
                })
                await websocket.send(state_msg)
                await asyncio.sleep(TICK_RATE)
        except: pass

    try:
        await asyncio.gather(primaj_poruke(), game_loop())
    finally:
        # Fix #1: Logovanje imena umesto ID-a
        if websocket in connected_clients:
            ime_igraca = connected_clients[websocket]["ime"]
            del connected_clients[websocket]
            log(f"Igrac '{ime_igraca}' je napustio igru. Preostalo: {len(connected_clients)}")

def init_viruses():
    global virus_list
    virus_list = []
    for _ in range(18):
        virus_list.append({
            "x": random.uniform(200, WORLD-200), 
            "y": random.uniform(200, WORLD-200), 
            "mass": 100, 
            "r": 35  # SMANJENO SA 60 NA 35 (Igrač puca tek kada je veći od ovoga)
        })
    log("Inicijalizovano 18 virusa.")

async def main():
    init_food()
    init_viruses() 
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        log("WebSocket server startovan na portu 8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())