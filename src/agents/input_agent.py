from .base_agent import BasePokerAgent


class InputAgent(BasePokerAgent):
    def __init__(self, seed: int = None, name: str = "Input Agent"):
        super().__init__(seed, name)

    def decide_action(self, game_state):
        print(game_state)
        valid_actions = ('match', 'increase', 'fold')
        action = ''
        amount = None
        while action not in valid_actions:
            action = input("Input your action (match/increase/fold/idle):")
        if action == 'increase':
            while not amount:
                amount_input = input("Input the amount of chips you want to increase to:")
                try:
                    amount = abs(int(amount_input))
                except:
                    pass
        if not amount:
            amount = 0
        return {'action': action, 'amount': amount}