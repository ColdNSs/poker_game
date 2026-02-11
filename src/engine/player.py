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

    def __repr__(self):
        return f"{self.name} ({self.agent.name})"

    def game_start(self, start_state):
        self.agent.game_start(start_state)

    def decide_action(self, game_state):
        self.agent.decide_action(game_state)

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

    def bet(self, stack: ChipStack, amount: int):
        if amount < 0:
            raise ValueError("Cannot bet negative chips")

        # Required bet is larger than what left in stack, automatically go all-in
        if amount >= self.stack.amount:
            amount = self.stack.amount
            self.hand_status = 'all_in'

        stack.add(self.stack.pop(amount))
        self.unresolved_chips += amount
        return amount


