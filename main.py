import json
import logging
import redis
import uuid
from asyncio import Event
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from rq import Queue, Retry

from battle_worker import resolve_battle

app = FastAPI()
stop_event = Event()
logging.basicConfig(level=logging.INFO)

REDIS_URL = "redis://localhost:6379"
API_KEY = "supersecretapikey"
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
battle_queue = Queue('battle_queue', connection=redis_client)

# Simple API key authentication
async def auth(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# Models
class PlayerCreate(BaseModel):
    name: str = Field(max_length=20)
    description: str = Field(max_length=1000)
    gold: int = Field(le=1e9)
    silver: int = Field(le=1e9)
    attack: int = Field(ge=0)
    defense: int = Field(ge=0)
    hit_points: int = Field(ge=1)

class Player(PlayerCreate):
    id: str

class BattleRequest(BaseModel):
    attacker_id: str
    defender_id: str

class PlayerLock:
    def __init__(self, player_id: str, ttl: int = 5):
        self.key = f"lock:player:{player_id}"
        self.ttl = ttl
        self.token = str(uuid.uuid4())

    def acquire(self) -> bool:
        return redis_client.set(self.key, self.token, nx=True, ex=self.ttl) is not None

    def release(self):
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        redis_client.eval(script, 1, self.key, self.token)

class PlayerLocked(Exception):
    pass

# Constants
PLAYER_KEY_PREFIX = "player:"


# Endpoints
@app.post("/players", response_model=Player, dependencies=[Depends(auth)])
async def create_player(player: PlayerCreate):
    player_id = str(uuid.uuid4())

    player_data = Player(
        id=player_id,
        name=player.name,
        description=player.description,
        gold=player.gold,
        silver=player.silver,
        attack=player.attack,
        defense=player.defense,
        hit_points=player.hit_points)
    redis_client.set(
        PLAYER_KEY_PREFIX + player_id,
        json.dumps(player_data.model_dump()))

    redis_client.zadd("leaderboard", {player_id: 0})
    return player_data


@app.get("/leaderboard", dependencies=[Depends(auth)])
async def get_leaderboard():
    data = redis_client.zrevrange("leaderboard", 0, 9, withscores=True)

    return [
        {"rank": i + 1, "player_id": pid, "score": int(score)}
        for i, (pid, score) in enumerate(data)]


@app.post("/battles", dependencies=[Depends(auth)])
async def submit_battle(b: BattleRequest):
    if b.attacker_id == b.defender_id:
        raise HTTPException(400, "Same player")
    attacker_data = json.loads(redis_client.get(PLAYER_KEY_PREFIX + b.attacker_id))
    defender_data = json.loads(redis_client.get(PLAYER_KEY_PREFIX + b.defender_id))
    if not attacker_data or not defender_data:
        raise HTTPException(404, "Player not found")
    job = battle_queue.enqueue(manage_battle, attacker_data, defender_data, retry=Retry(max=3, interval=[1, 2, 3]))
    return {"status": "queued", "battle_id": job.id}


def manage_battle(attacker, defender):
    if not attacker or not defender:
        raise ValueError("Attacker or defender is None")
    lock_attacker = PlayerLock(attacker["id"], ttl=10)
    lock_defender = PlayerLock(defender["id"], ttl=10)
    lock = sorted([lock_attacker, lock_defender], key=lambda x: x.key)
    acquired = []
    try:

        for l in lock:
            if not l.acquire():
                raise PlayerLocked(f"Player {l.key} is locked.")
            acquired.append(l)

        logging.info(f"Battle started between {attacker} and {defender}.")
        winner, loser, gold_loot, silver_loot, log = resolve_battle(attacker, defender)
        logging.info(f"Battle result: {winner['name']} defeated {loser['name']} - Looted {gold_loot} gold and {silver_loot} silver.")
        logging.info("Battle log:")
        for entry in log:
            logging.info(entry)

        # Update winner's resources
        winner["gold"] += gold_loot
        winner["silver"] += silver_loot
        # Update loser's resources
        loser["gold"] -= gold_loot
        loser["silver"] -= silver_loot

        # Save updated players
        redis_client.set(PLAYER_KEY_PREFIX + winner["id"], json.dumps(winner))
        redis_client.set(PLAYER_KEY_PREFIX + loser["id"], json.dumps(loser))

        # Update leaderboard score
        redis_client.zincrby("leaderboard", gold_loot + silver_loot, winner["id"])

        return winner, loser, gold_loot, silver_loot, log

    except Exception as e:
        logging.error(f"Error during battle: {e}")
        return None

    finally:
        for l in acquired:
            l.release()