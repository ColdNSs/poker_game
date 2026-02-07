from seed_gen import generate_game_seed, derive_deck_seed, derive_order_seed, derive_agent_seeds
from player import Player
from treys import Card, Deck, Evaluator
from random import Random
from chip_stack import ChipStack


class PokerGame:
    def __init__(self, game_id: int, players: set[Player], initial_chips_per_player: int = 1000 ,game_seed: int = None):
        self.game_id = game_id
        self.players = players
        self.game_seed = generate_game_seed(game_seed)
        self.hand_count = 0

        # Derive seeds from the game seed
        deck_seed = derive_deck_seed(self.game_seed)
        order_seed = derive_order_seed(self.game_seed)
        agent_seeds = derive_agent_seeds(self.game_seed, len(self.players))

        # Instantiate a deck
        self.deck = Deck(deck_seed)

        # Shuffle player order
        rng = Random(order_seed)
        self.player_list = sorted(self.players, key=lambda p: p.player_id)
        rng.shuffle(self.player_list)

        # Initiate agent seeds
        for player in self.player_list:
            player.agent.init_seed(agent_seeds.pop())

        # Initiate stacks
        # Only time chips are added to the whole system
        self.bank = ChipStack(amount=initial_chips_per_player * len(self.players))
        # Chips are transferred between stacks
        for player in self.player_list:
            player.stack.add(self.bank.pop(initial_chips_per_player))

        self.step()

    def step(self):
        pass