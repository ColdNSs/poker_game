from agents.base_agent import BasePokerAgent
from chip_stack import ChipStack


class Player:
    def __init__(self, player_id: int, agent: BasePokerAgent):
        self.player_id = player_id
        self.agent = agent
        self.stack = ChipStack(amount=0)
        self.status_in_game = 'active' # active / eliminated
        self.status_in_hand = 'active' # active / folded / all-in

    def decide_action(self, game_state):
        self.agent.decide_action(game_state)

    def hand_ended(self, hand_history):
        self.agent.hand_ended(hand_history)