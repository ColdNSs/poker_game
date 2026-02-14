from agents.base_agent import BasePokerAgent
from chip_stack import ChipStack


class Player:
    def __init__(self, player_id: int, agent: BasePokerAgent, name: str = "Player"):
        self.player_id = player_id
        self.name = name
        self.agent = agent
        self.stack = ChipStack(amount=0)
        self.game_status = 'alive' # alive / eliminated
        self.hand_status = 'active' # active / folded / all-in
        self.unresolved_chips = 0 # Total committed chips this stage
        self.total_bet_this_hand = 0
        self.total_gain_this_hand = 0
        self.can_raise = True
        self.hole_cards = []
        self.score = 0
        self.rank = None

    def __repr__(self):
        return f"{self.name} ({self.agent.name})"

    # This function should only be called at the end of a hand
    def check_alive(self):
        if self.stack.amount == 0:
            self.game_status = 'eliminated'
            return
        self.hand_status = 'active'
        self.total_bet_this_hand = 0
        self.total_gain_this_hand = 0

    def stage_start(self):
        assert self.unresolved_chips == 0
        self.can_raise = True

    def receive_hole_cards(self, hole_cards: list[int]):
        if len(hole_cards) != 2:
            raise ValueError("Wrong hole card amount")
        self.hole_cards = hole_cards

    def resolve(self, amount: int):
        if amount > self.unresolved_chips:
            raise ValueError(f"Cannot resolve more than current unresolved chips"
                             f"{amount} > {self.unresolved_chips}")
        self.unresolved_chips -= amount

    def gain(self, stack: ChipStack, amount: int):
        if amount < 0:
            raise ValueError("Cannot gain negative chips")
        self.stack.add(stack.pop(amount))
        self.total_gain_this_hand += amount

    def is_actable(self, max_bet):
        assert self.unresolved_chips <= max_bet
        if self.hand_status == 'folded' or self.hand_status == 'all-in':
            return False

        if self.unresolved_chips != max_bet:
            return True

        if self.can_raise:
            return True

        return False

    def fold(self):
        self.hand_status = 'folded'

    def set_raise(self):
        self.can_raise = True

    def update_score(self, score: int):
        if score < 1:
            raise ValueError("Score evaluated by treys should be at least 1")
        self.score = score

    def update_rank(self, rank: int):
        if rank < 1:
            raise ValueError("Assigned rank should be at least 1")
        self.rank = rank

    def bet(self, stack: ChipStack, amount: int):
        if amount < 0:
            raise ValueError("Cannot bet negative chips")

        # Required bets is larger than what left in stack, automatically go all-in
        if amount >= self.stack.amount:
            amount = self.stack.amount
            self.hand_status = 'all-in'

        stack.add(self.stack.pop(amount))
        self.unresolved_chips += amount
        self.total_bet_this_hand += amount
        self.can_raise = False
        return amount


