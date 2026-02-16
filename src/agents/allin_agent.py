from .base_agent import BasePokerAgent


class AllInAgent(BasePokerAgent):
    def __init__(self, seed: int = None, name: str = "All-in Agent"):
        super().__init__(seed, name)

    def decide_action(self, game_state):
        action = {
            'action': 'increase',
            'amount': game_state['your_status']['stack']
        }
        return action