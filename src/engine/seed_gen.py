import random
import hmac
import hashlib
import struct


def generate_game_seed(seed: int = None) -> int:
    """
        Select a 32-bit game seed and cap it under 2**32 - 1, or generate one.

        Args:
            seed (int): The selected seed. Default to None for a generated seed.

        Returns:
            int: A 32-bit integer seed.
    """
    # If a seed is selected for the game: Cap it under 2**32 - 1
    if seed:
        return abs(seed) & 0xFFFFFFFF
    # Else: generate a seed between 0 and 2**32 - 1
    return random.randint(0, 0xFFFFFFFF)

def derive_seed(game_seed: int, namespace: int) -> int:
    """
        Derive a deterministic 32-bit seed from a master game seed and a namespace.

        Args:
            game_seed (int): The master game seed for the current game.
            namespace (int): A number distinguishing deck, agents, or other RNG streams.

        Returns:
            int: A 32-bit integer seed for initializing a Random object.
    """
    if not (0 <= game_seed <= 0xFFFFFFFF):
        raise ValueError("Game seed must be a 32-bit integer")

    # '>I' means Big-Endian Unsigned Int (4 bytes)
    # '>Q' means Big-Endian Unsigned Long Long (8 bytes) - allows large namespaces
    key_bytes = struct.pack('>I', game_seed)
    data_bytes = struct.pack('>Q', namespace)

    h = hmac.new(key_bytes, data_bytes, hashlib.sha256)
    digest = h.digest()  # Returns 32 bytes (256 bits)

    # To get a 64-bit seed, change slice to [:8] and unpack with '>Q'
    derived_seed = struct.unpack('>I', digest[:4])[0]

    return derived_seed

def derive_deck_seed(game_seed: int) -> int:
    return derive_seed(game_seed, 0)

def derive_order_seed(game_seed: int) -> int:
    return derive_seed(game_seed, 1)

def derive_agent_seeds(game_seed: int, agent_count: int = 10) -> list[int]:
    agent_seeds = []
    for agent_id in range(agent_count):
        agent_seeds.append(derive_seed(game_seed, agent_id + 1000))
    return agent_seeds

if __name__ == '__main__':
    example_game_seed = generate_game_seed(42)
    example_deck_seed = derive_deck_seed(example_game_seed)
    example_order_seed = derive_order_seed(example_game_seed)
    example_player_seeds = derive_agent_seeds(example_game_seed, 8)

    print(example_game_seed, example_deck_seed, example_order_seed, example_player_seeds)