from player import Player
from chip_stack import ChipStack
from treys import Deck
from agents.input_agent import InputAgent


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
        self.pot_stacks = []
        main_pot = {
            'stack': ChipStack(),
            'eligible_players': self.player_list.copy()
        }
        self.pot_stacks.append(main_pot)

    # Yield Dealer, Small Blind, Big Blind and Under the Gun
    def get_positions(self):
        n = len(self.player_list)

        if n == 2:
            yield self.player_list[0]   # Dealer
            yield self.player_list[0]   # Small Blind
            yield self.player_list[1]   # Big Blind
            yield self.player_list[0]   # Under the Gun
            return

        yield self.player_list[0]       # Dealer
        yield self.player_list[1]       # Small Blind
        yield self.player_list[2]       # Big Blind
        yield self.player_list[3 % n]   # Under the Gun

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
                    print(f"{player.name} put {pot_increase} chips into current pot")
                    player.unresolved_chips -= pot_increase

            # Create a new side pot that excludes this player
            new_side_pot = {
                'stack': ChipStack(),
                'eligible_players': non_all_iners + all_iners
            }
            print(f"New pot created. Eligible players: {new_side_pot['eligible_players']}")
            self.pot_stacks.append(new_side_pot)

        # For players who don't all-in just move their chips to the current pot
        for player in non_all_iners:
            self.pot_stacks[-1]['stack'].add(stack.pop(player.unresolved_chips))
            player.unresolved_chips = 0

        assert stack.amount == 0
        print(self.pot_stacks)

    def collect_antes(self):
        stack = ChipStack()

        for player in self.player_list:
            player.stage_start()
            player.bet(stack, self.ante)

        self.add_to_pots(stack)

    def collect_blinds(self):
        stack = ChipStack()
        _, small_blind, big_blind, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        small_blind.bet(stack, self.small_blind)
        big_blind.bet(stack, self.big_blind)
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
    example_hand = Hand(example_list, 0, 0, 3, 1, 2,example_deck)

    example_hand.collect_antes()
    example_hand.collect_blinds()