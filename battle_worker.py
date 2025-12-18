import random
from math import ceil

def resolve_battle(attacker: dict, defender: dict):
    log = []
    hp_a, hp_d = attacker["hit_points"], defender["hit_points"]

    while hp_a > 0 and hp_d > 0:

        # Attacker's turn
        hp_d = resolve_turn(attacker, defender, hp_a, hp_d, log)
        if hp_d <= 0:
            break

        # Defender's turn
        hp_a = resolve_turn(defender, attacker, hp_d, hp_a, log)

    winner, loser = (attacker, defender) if hp_a > 0 else (defender, attacker)
    loot_percent = random.uniform(0.05, 0.1)
    gold_loot = ceil(loser["gold"] * loot_percent)
    silver_loot = ceil(loser["silver"] * loot_percent)

    return winner, loser, gold_loot, silver_loot, log


def resolve_turn(attacker: dict, defender: dict, attacker_hp:int, defender_hp: int, log: list):
    hit = random.randint(0, 100) > defender["defense"]
    if hit:
        damage = int(max(attacker["attack"] * attacker_hp / attacker["hit_points"], attacker["attack"] * 0.5))
        defender_hp -= damage
        log.append(f"{attacker['name']} hits {defender['name']} for {damage} damage - has {max(defender_hp, 0)} left!")
    else:
        log.append(f"{attacker['name']} misses {defender['name']}!")
    return defender_hp
