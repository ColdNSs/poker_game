from seed_gen import generate_game_seed, derive_deck_seed, derive_order_seed, derive_agent_seeds
from player import Player
from treys import Card, Deck, Evaluator
from random import Random
from chip_stack import ChipStack
from copy import deepcopy
from hand import Hand

class PokerGame:
    def __init__(self, game_id: int, players: set[Player], initial_chips_per_player: int = 200 ,game_seed: int = None):
        if not (2 <= len(players) <= 10):
            raise ValueError("Game requires between 2 and 10 players")

        self.game_id = game_id
        self.players = players
        self.game_seed = generate_game_seed(game_seed)
        self.hand_count = 0     # +1 after each hand
        self.round_count = 0    # +1 after each time dealer button returns to its initial position
        self.dealer_button = 0
        self.ante = 0
        self.small_blind = 1
        self.big_blind = 2
        self.alive_count = len(self.players)

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

        self.game_start(initial_chips_per_player)
        # self.run_game()

    def game_start(self, initial_chips_per_player: int):
        player_states = []
        for order, player in enumerate(self.player_list):
            player_state = {
                "player_id": player.player_id,
                "stack": player.stack.amount,
                "order": order,
                "game_status": player.game_status
            }
            player_states.append(player_state)

        start_state = {
            "initial_stack_per_player": initial_chips_per_player,
            "player_count": len(self.players),
            "your_id": None,
            "players": player_states
        }

        for player in self.player_list:
            isolated_state = deepcopy(start_state)
            isolated_state['your_id'] = player.player_id
            player.game_start(isolated_state)

    def run_game(self):
        winner = None
        while not winner:
            # Rotate the player list so that dealer is at index 0 in the new list
            hand_players = self.player_list[self.dealer_button:] + self.player_list[:self.dealer_button]
            # Exclude eliminated players
            hand_players = [player for player in hand_players if player.game_status == 'alive']
            assert 2 <= len(hand_players) <= 10

            hand = Hand(hand_players,
                        self.hand_count,
                        self.round_count,
                        self.ante,
                        self.small_blind,
                        self.big_blind,
                        self.deck)
            hand.run_hand()

            self.hand_count += 1

            for player in hand_players:
                player.check_alive()

            alive_players = [player for player in hand_players if player.game_status == 'alive']
            self.alive_count = len(alive_players)
            assert self.alive_count > 0
            if self.alive_count == 1:
                winner = alive_players[0]

            found_next_alive_player = False
            while not found_next_alive_player:
                self.dealer_button += 1
                if self.dealer_button == len(self.player_list):
                    self.dealer_button = 0
                    self.round_count += 1

                if self.player_list[self.dealer_button] == 'alive':
                    found_next_alive_player = True

