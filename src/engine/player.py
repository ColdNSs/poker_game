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
        self.can_raise = True
        self.hole_cards = []

    def __repr__(self):
        return f"{self.name} ({self.agent.name})"

    def game_start(self, start_state):
        self.agent.game_start(start_state)

    def decide_action(self, game_state):
        action = self.agent.decide_action(game_state)
        return action

    def hand_ended(self, hand_history):
        self.agent.hand_ended(hand_history)

    # This function should only be called at the end of a hand
    def check_alive(self):
        if self.stack.amount == 0:
            self.game_status = 'eliminated'
            return
        self.hand_status = 'active'

    def stage_start(self):
        assert self.unresolved_chips == 0
        self.can_raise = True

    def receive_hole_cards(self, hole_cards: list[int]):
        if len(hole_cards) != 2:
            raise ValueError("Wrong hole card amount")
        self.hole_cards = hole_cards

    def resolve(self, amount: int):
        if amount <= self.unresolved_chips:
            raise ValueError(f"Cannot resolve more than current unresolved chips"
                             f"{amount} > {self.unresolved_chips}")
        self.unresolved_chips -= amount

    def is_actable(self, max_bet):
        assert self.unresolved_chips <= max_bet
        if self.hand_status == 'folded' or self.hand_status == 'all_in':
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

    def bet(self, stack: ChipStack, amount: int):
        if amount < 0:
            raise ValueError("Cannot bet negative chips")

        # Required bet is larger than what left in stack, automatically go all-in
        if amount >= self.stack.amount:
            amount = self.stack.amount
            self.hand_status = 'all_in'

        stack.add(self.stack.pop(amount))
        self.unresolved_chips += amount
        self.can_raise = False
        return amount


