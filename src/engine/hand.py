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
    def deal_cards(self, index: int):
        self.deck.shuffle()

        for _ in range(len(self.player_list)):
            hole_cards = self.deck.draw(2)
            self.player_list[index].receive_hole_cards(hole_cards)
            to_str = Card.ints_to_pretty_str(hole_cards)
            print(f"Dealt hole cards to {self.player_list[index]}: {to_str}")
            index += 1
            if index == len(self.player_list):
                index = 0

        self.community_cards = self.deck.draw(5)
        to_str = Card.ints_to_pretty_str(self.community_cards)
        print(f"Dealt community cards: {to_str}")

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
                    self.pot_stacks[-1]['stack'].add(stack.pop(pot_increase))
                    player.unresolved_chips -= pot_increase

            # Create a new side pot that excludes this player
            new_side_pot = {
                'stack': ChipStack(),
                'eligible_players': non_all_iners + all_iners
            }
            self.pot_stacks.append(new_side_pot)

        # For players who don't all-in just move their chips to the current pot
        for player in non_all_iners:
            self.pot_stacks[-1]['stack'].add(stack.pop(player.unresolved_chips))
            player.unresolved_chips = 0

        assert stack.amount == 0
        print(self.pot_stacks)

    def get_max_bet(self):
        return max(p.unresolved_chips for p in self.player_list)

    def is_betting_round_over(self):
        # Folded players are out; All-In players are locked in
        active_players = [p for p in self.player_list
                          if p.hand_status != 'folded'
                          and p.hand_status != 'all_in']

        # Edge Case: If 0 or 1 active players remain, the betting round is essentially over
        # The game might continue to showdown if there are all-ins, but no more betting acts
        if len(active_players) < 2:
            return True

        # Determine the "Target Amount" to match
        max_bet = self.get_max_bet()

        # Check every active player
        for player in active_players:
            # Condition A: Have they matched the money?
            if player.unresolved_chips != max_bet:
                return False

            # Condition B: Can they perform a raise?
            if not player.can_raise:
                return False

        return True

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
        self.deal_cards(index=sb)

        # Start a betting stage
        current_player = utg
        retry_count = 0         # Times failed to find the next actable player
        max_bet = self.big_blind
        min_raise = self.big_blind
        while retry_count < len(self.player_list) - 1:
            # Pick the next player in order
            player = self.player_list[current_player]
            if player.is_actable(max_bet):
                retry_count = 0

                game_status = {}
                action = self.player_list[current_player].decide_action(game_status)

                if action['action'] == 'fold':
                    player.fold()

                elif action['action'] == 'match':
                    player.bet(stack, max_bet - player.unresolved_chips)

                else:
                    raise InvalidActionError(f"Undefined action '{action['action']}'")

                max_bet = self.get_max_bet()
            else:
                retry_count += 1

            current_player += 1
            if current_player == len(self.player_list):
                current_player = 0



        self.add_to_pots(stack)

    def run_hand(self):
        pass


if __name__ == '__main__':
    alice = Player(0, InputAgent(), "Alice")
    bob = Player(0, InputAgent(), "Bob")
    clementine = Player(0, InputAgent(), "Clementine")
    dave = Player(0, InputAgent(), "Dave")

    alice.stack.add(1)
    bob.stack.add(5)
    clementine.stack.add(10)
    dave.stack.add(10)

    example_list = [alice, bob, clementine, dave]
    example_deck = Deck()
    example_hand = Hand(example_list, 0, 0, 3, 1, 2, example_deck)

    example_hand.collect_antes()
    example_hand.run_preflop()