from player import Player
from chip_stack import ChipStack


class Hand:
    def __init__(
            self,
            player_list: list[Player],
            hand_id: int,
            round_id: int,
            ante: int,
            small_blind: int,
            big_blind: int
    ):
        self.player_list = player_list
        self.hand_id = hand_id
        self.round_id = round_id
        self.ante = ante
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.pot_stacks = []
        main_pot = {
            'stack': ChipStack(),
            'eligible_players': self.player_list.copy()
        }
        self.pot_stacks.append(main_pot)

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
            # Current pot will be empty, remove it
            if pot_increase == 0:
                assert self.pot_stacks[-1]['stack'].amount == 0
                self.pot_stacks.pop()
            # Current pot will not be empty, add chips to it
            else:
                for player in contributors:
                    self.pot_stacks[-1]['stack'].add(stack.pop(pot_increase))
                    player.unresolved_chips -= pot_increase

            # Create a new side pot that excludes this player
            new_side_pot = {
                'stack': ChipStack(),
                'eligible_players': non_all_iners + all_iners
            }
            self.pot_stacks.append(new_side_pot)

        # Move chips to the current pot
        for player in non_all_iners:
            self.pot_stacks[-1]['stack'].add(stack.pop(player.unresolved_chips))
            player.unresolved_chips = 0

        assert stack.amount == 0

    def collect_antes(self):
        stack = ChipStack()
        for player in self.player_list:
            player.stage_start()
            player.bet(stack, self.ante)
        self.add_to_pots(stack)

    def run_hand(self):
        pass