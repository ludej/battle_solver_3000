import pytest
from main import manage_battle
import logging
logging.basicConfig(level=logging.INFO)
import uuid
import httpx

BASE_URL = "http://localhost:8000"
API_KEY = "supersecretapikey"

def player(**kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "name": "Player",
        "description": "A brave warrior",
        "hit_points": 100,
        "attack": 20,
        "defense": 10,
        "gold": 100,
        "silver": 50}
    defaults.update(kwargs)
    return defaults

def test_manage_battle_attacker_wins():
    attacker = player(defense = 100)
    defender = player(hit_points = 1)

    winner, loser, gold, silver, _ = manage_battle(attacker, defender)
    assert winner['id'] == attacker['id']
    assert loser['id'] == defender['id']
    assert gold > 0
    assert silver > 0

def test_manage_battle_defender_wins():
    attacker = player(hit_points = 1)
    defender = player(defense = 100)

    winner, loser, gold, silver, _ = manage_battle(attacker, defender)
    assert winner['id'] == defender['id']
    assert loser['id'] == attacker['id']
    assert gold > 0
    assert silver > 0

def test_same_user_battle():
    attacker = player()
    defender = attacker  # Same player

    result = manage_battle(attacker, defender)
    assert result is None

def test_attacker_is_none():
    attacker = None
    defender = player()

    with pytest.raises(ValueError):
        manage_battle(attacker, defender)

def test_defender_is_none():
    attacker = player()
    defender = None

    with pytest.raises(ValueError):
        manage_battle(attacker, defender)

def test_battle_logging(caplog):
    attacker = player(defense = 100)
    defender = player(hit_points = 1)

    with caplog.at_level(logging.INFO):
        manage_battle(attacker, defender)

    assert any("Battle started between" in message for message in caplog.messages)
    assert any("Battle result:" in message for message in caplog.messages)


def test_player_zero_hit_points():
    attacker = player(hit_points = 0)
    defender = player()

    winner, loser, gold, silver, _ = manage_battle(attacker, defender)
    assert winner['id'] == defender['id']
    assert loser['id'] == attacker['id']
    assert gold > 0
    assert silver > 0

def test_player_negative_hit_points():
    attacker = player(hit_points = -10)
    defender = player()

    winner, loser, gold, silver, _ = manage_battle(attacker, defender)
    assert winner['id'] == defender['id']
    assert loser['id'] == attacker['id']
    assert gold > 0
    assert silver > 0

def test_create_player():
    headers = {"X-API-KEY": API_KEY}
    player_data = player(name="TestPlayer", description="A test player")
    response = httpx.post(f"{BASE_URL}/players", json=player_data, headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "TestPlayer"
    assert data["description"] == "A test player"
    assert data["gold"] == player_data["gold"]
    assert data["silver"] == player_data["silver"]
    assert data["attack"] == player_data["attack"]
    assert data["defense"] == player_data["defense"]
    assert data["hit_points"] == player_data["hit_points"]
    assert "id" in data


def test_create_player_too_rich_in_gold():
    headers = {"X-API-KEY": API_KEY}
    player_data = player(gold=1e10, silver=500_000)
    response = httpx.post(f"{BASE_URL}/players", json=player_data, headers=headers)
    assert response.status_code == 422
    assert "should be less than or equal to 1000000000" in response.text.lower()


def test_create_player_too_rich_in_silver():
    headers = {"X-API-KEY": API_KEY}
    player_data = player(gold=500_000, silver=1e10)
    response = httpx.post(f"{BASE_URL}/players", json=player_data, headers=headers)
    assert response.status_code == 422
    assert "should be less than or equal to 1000000000" in response.text.lower()


def test_end_to_end():
    headers = {"X-API-KEY": API_KEY}
    attacker_data = player(name="Attacker")
    defender_data = player(name="Defender")

    response_a = httpx.post(f"{BASE_URL}/players", json=attacker_data, headers=headers)
    response_d = httpx.post(f"{BASE_URL}/players", json=defender_data, headers=headers)
    assert response_a.status_code == 200, response_a.text
    assert response_d.status_code == 200, response_d.text

    attacker_id = response_a.json()["id"]
    defender_id = response_d.json()["id"]

    battle_request = {"attacker_id": attacker_id, "defender_id": defender_id}
    battle_response = httpx.post(f"{BASE_URL}/battles", json=battle_request, headers=headers)
    assert battle_response.status_code == 200
    battle_data = battle_response.json()
    assert battle_data["status"] == "queued"
    assert "battle_id" in battle_data