from player import Player
from chip_stack import ChipStack
from treys import Card, Deck
from agents.input_agent import InputAgent


class InvalidActionError(Exception):
    """Raised when an agent returns an invalid or illegal action."""
    pass


class Hand:
    def __init__(
            self,
            player_list: list[Player],
            hand_id: int,
            round_id: int,
            ante: int,
            small_blind: int,
            big_blind: int,
            deck: Deck
    ):
        assert 2 <= len(player_list) <= 10
        self.player_list = player_list
        self.hand_id = hand_id
        self.round_id = round_id
        self.ante = ante
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.deck = deck
        self.community_cards = []
        self.pot_stacks = []
        main_pot = {
            'stack': ChipStack(),
            'eligible_players': self.player_list.copy()
        }
        self.pot_stacks.append(main_pot)

    # Yield indexes of Dealer, Small Blind, Big Blind and Under the Gun
    def get_positions(self):
        n = len(self.player_list)

        if n == 2:
            yield 0     # Dealer
            yield 0     # Small Blind
            yield 1     # Big Blind
            yield 0     # Under the Gun
            return

        yield 0         # Dealer
        yield 1         # Small Blind
        yield 2         # Big Blind
        yield 3 % n     # Under the Gun

    # Deal cards, usually start with small blind
    def deal_hole_cards(self, index: int):
        self.deck.shuffle()

        for _ in range(len(self.player_list)):
            hole_cards = self.deck.draw(2)
            self.player_list[index].receive_hole_cards(hole_cards)
            to_str = Card.ints_to_pretty_str(hole_cards)
            print(f"Dealt hole cards to {self.player_list[index]}: {to_str}")
            index += 1
            if index == len(self.player_list):
                index = 0

    def deal_community_cards(self, amount: int):
        if amount < 0:
            raise ValueError("Cannot deal negative amount of community cards")
        self.community_cards = self.community_cards + self.deck.draw(amount)
        to_str = Card.ints_to_pretty_str(self.community_cards)
        print(f"All community cards: {to_str}")

    # Extremely messy codes here. Should exist a better implementation
    def add_to_pots(self, stack: ChipStack):
        contributors = [player for player in self.player_list if player.unresolved_chips != 0]
        all_iners = [player for player in contributors if player.hand_status == 'all_in']
        non_all_iners = [player for player in contributors if player not in all_iners]

        # Sorted by total committed chips this stage, from high to low
        all_iners.sort(key=lambda p: p.unresolved_chips, reverse=True)

        # When a player all-ins, move chips to the current pot and create a new pot that excludes this player
        while all_iners:
            least_committed = all_iners.pop()
            pot_increase = least_committed.unresolved_chips
            if pot_increase == 0:
                # Current pot will be empty, remove it
                assert self.pot_stacks[-1]['stack'].amount == 0
                self.pot_stacks.pop()
            else:
                # Current pot will not be empty, add chips to it
                for player in non_all_iners + all_iners + [least_committed]:
                    amount = min(pot_increase, player.unresolved_chips)
                    self.pot_stacks[-1]['stack'].add(stack.pop(amount))
                    player.resolve(amount)

            # Create a new side pot that excludes this player
            new_side_pot = {
                'stack': ChipStack(),
                'eligible_players': non_all_iners + all_iners
            }
            self.pot_stacks.append(new_side_pot)

        # For players who don't all-in just move their chips to the current pot
        for player in non_all_iners:
            self.pot_stacks[-1]['stack'].add(stack.pop(player.unresolved_chips))
            player.resolve(player.unresolved_chips)

        assert stack.amount == 0
        print(self.pot_stacks)

    def get_max_bet(self):
        return max(p.unresolved_chips for p in self.player_list)

    def betting_stage(self, stack: ChipStack, current_player: int, bet_to_call: int, min_raise: int):
        retry_count = 0     # Times failed to find the next active player
        while retry_count < len(self.player_list) - 1:
            # Pick the next player in order
            player = self.player_list[current_player]
            actable = player.is_actable(bet_to_call)
            if actable:

                game_status = {'your_id': player.player_id}
                action = self.player_list[current_player].decide_action(game_status)

                if action['action'] == 'fold':
                    player.fold()

                elif action['action'] == 'match':
                    player.bet(stack, bet_to_call - player.unresolved_chips)

                elif action['action'] == 'increase':
                    can_raise = player.can_raise
                    # Call first
                    player.bet(stack, bet_to_call - player.unresolved_chips)
                    if can_raise:
                        # This is the amount player wants to increase by, not including how much they have to call
                        amount = max(action['amount'], min_raise)
                        # Raise
                        actual_raise = player.bet(stack, amount)
                        # When it's a full raise
                        if actual_raise >= min_raise:
                            min_raise = actual_raise
                            # Open raise for everyone else
                            for p in self.player_list:
                                if p is player:
                                    continue
                                p.set_raise()
                        # Update bet to call. It only goes up never goes down
                        bet_to_call = max(self.get_max_bet(), bet_to_call)

                else:
                    raise InvalidActionError(f"Undefined action '{action['action']}'")

            # If player is still active, next retry starts with retry count set to 0
            if actable and not player.hand_status == 'folded':
                retry_count = 0
            else:
                retry_count += 1

            current_player += 1
            if current_player == len(self.player_list):
                current_player = 0

    def get_competing_players(self):
        """Returns all players who have NOT folded."""
        return [p for p in self.player_list if p.hand_status != 'folded']

    def check_uncontested_win(self):
        """
        Checks if only one player remains.
        If yes, awards them the pot immediately.
        Returns True if the hand ended, False otherwise.
        """
        competing_players = self.get_competing_players()

        if len(competing_players) == 1:
            winner = competing_players[0]
            for pot in self.pot_stacks:
                if pot['stack'].amount == 0:
                    continue
                assert winner in pot['eligible_players']
                winner.stack.add(pot['stack'].pop(pot['stack'].amount))
            # Log the win
            print(f"Hand ended. {winner} wins by everyone else folding")

            return True

        return False

    def collect_antes(self):
        stack = ChipStack()

        for player in self.player_list:
            player.stage_start()
            player.bet(stack, self.ante)

        self.add_to_pots(stack)

    def run_preflop(self):
        stack = ChipStack()
        _, sb, bb, utg = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Collect blinds
        self.player_list[sb].bet(stack, self.small_blind)
        self.player_list[bb].bet(stack, self.big_blind)
        # Blinds still get a chance to act voluntarily
        self.player_list[sb].set_raise()
        self.player_list[bb].set_raise()

        # Deal cards, starting with small blind
        self.deal_hole_cards(index=sb)

        # Start Pre-flop betting stage
        current_player = utg
        bet_to_call = self.big_blind    # During Pre-flop, min bet to call = big blind, no matter how much the BB paid
        min_raise = self.big_blind
        self.betting_stage(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_flop(self):
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 3 community cards
        self.deal_community_cards(3)

        # Start Flop betting stage
        current_player = sb # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_stage(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_turn(self):
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 1 community card
        self.deal_community_cards(1)

        # Start Turn betting stage
        current_player = sb  # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_stage(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_river(self):
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 1 community card
        self.deal_community_cards(1)

        # Start River betting stage
        current_player = sb  # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_stage(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def showdown(self):
        pass

    def run_hand(self):
        self.collect_antes()
        stages = [
            self.run_preflop,
            self.run_flop,
            self.run_turn,
            self.run_river
        ]

        # Iterate through each stage
        for stage_method in stages:
            stage_method()  # Execute the deal and betting for this stage

            # Did everyone fold?
            if self.check_uncontested_win():
                return  # Exit run_hand immediately

        # If we survive all stages without a fold-win, it's a showdown
        self.showdown()


if __name__ == '__main__':
    alice = Player(0, InputAgent(), "Alice")
    bob = Player(1, InputAgent(), "Bob")
    clementine = Player(2, InputAgent(), "Clementine")
    dave = Player(3, InputAgent(), "Dave")

    alice.stack.add(10)
    bob.stack.add(6)
    clementine.stack.add(10)
    dave.stack.add(10)

    example_list = [alice, bob, clementine, dave]
    example_deck = Deck()
    example_hand = Hand(example_list, 0, 0, 3, 1, 2, example_deck)

    example_hand.collect_antes()
    example_hand.run_preflop()
    example_hand.check_uncontested_win()
    for p in example_list:
        print(p, p.stack)