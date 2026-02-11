from random import Random


class BasePokerAgent:
    def __init__(self, seed: int = None, name: str = "Base Agent"):
        self.name = name
        self.seed = None
        self._random = None
        self.init_seed(seed)

    def __repr__(self):
        return self.name

    def init_seed(self, seed: int):
        self.seed = seed
        self._random = Random(seed)

    def game_start(self, start_state):
        """
        Called when the game starts.
        Use this to create an internal database.
        """
        pass

    def decide_action(self, game_state):
        """
        Called when it is this bot's turn to act.
        Must return a valid action.
        """
        raise NotImplementedError

    def hand_ended(self, hand_history):
        """
        Called at the very end of a hand.
        Reveals cards of players who went to showdown.
        Use this to update your internal database of opponent tendencies.
        """
        pass