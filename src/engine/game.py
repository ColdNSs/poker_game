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

    def get_player_status(self, player: Player):
        player_status = {
            "player_id": player.player_id,
            "stack": player.stack.amount,
            "order": self.player_list.index(player)
        }
        return player_status

    def game_start(self, initial_chips_per_player: int):
        players = []
        for player in self.player_list:
            player_status = self.get_player_status(player)
            players.append(player_status)

        start_state = {
            "initial_stack_per_player": initial_chips_per_player,
            "player_count": len(self.players),
            "your_status": dict(),
            "players": players
        }

        for player in self.player_list:
            isolated_state = deepcopy(start_state)
            isolated_state['your_status'] = self.get_player_status(player)
            player.agent.game_start(isolated_state)

    def run_game(self):
        n_players = len(self.players)
        while True:
            # Dealer is at index 0 in the hand player list
            hand_players = self.player_list[self.dealer_button:] + self.player_list[:self.dealer_button]
            # Exclude eliminated players
            hand_players = [player for player in hand_players if player.game_status == 'alive']

            self.alive_count = len(hand_players)
            assert self.alive_count > 0
            if self.alive_count == 1:
                winner = hand_players[0]
                break

            hand = Hand(hand_players,
                        self.hand_count + 1,
                        self.ante,
                        self.small_blind,
                        self.big_blind,
                        self.deck)
            hand.run_hand()

            self.hand_count += 1

            # Rotate the dealer button
            found_next_alive_player = False
            while not found_next_alive_player:
                self.dealer_button = (self.dealer_button + 1) % n_players
                found_next_alive_player = self.player_list[self.dealer_button].game_status == 'alive'

        print(f"Game ended. Winner: {winner}")
