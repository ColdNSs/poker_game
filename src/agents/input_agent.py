from .base_agent import BasePokerAgent


class InputAgent(BasePokerAgent):
    def __init__(self, seed: int = None, name: str = "Input Agent"):
        super().__init__(seed, name)

    def game_start(self, start_state):
        print(start_state)

    def decide_action(self, game_state):
        print(game_state)
        valid_actions = ('match', 'increase', 'fold')
        action = ''
        amount = 0
        while action not in valid_actions:
            action = input("Input your action (match/increase/fold):")
        if action == 'increase':
            while not amount:
                amount_input = input("Input the amount of chips you want to increase:")
                try:
                    amount = abs(int(amount_input))
                except:
                    pass

        return {'action': action, 'amount': amount}