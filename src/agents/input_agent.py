from .base_agent import BasePokerAgent


class InputAgent(BasePokerAgent):
    def __init__(self, seed: int = None, name: str = "Input Agent", dollar_per_chip: int = 5):
        if dollar_per_chip < 1:
            raise ValueError("Dollar to chip ratio should at least be 1")
        super().__init__(seed, name)
        self.dollar_per_chip = dollar_per_chip

    def game_start(self, start_state):
        print(start_state)

    def decide_action(self, game_state):
        print(game_state)
        valid_actions = ('match', 'increase', 'fold')
        action = ''
        amount = 0
        while action not in valid_actions:
            cmd = input("Input your action (match/increase/fold):")
            to_list = cmd.split(' ')
            action = to_list[0]
            if action == 'increase':
                if len(to_list) > 1:
                    if to_list[1].isdigit():
                        amount = abs(int(to_list[1]))
                if not amount:
                    action = ''

        return {'action': action, 'amount': amount}

    def hand_ended(self, hand_history):
        print(hand_history)