from abc import ABC, abstractmethod


class BaseEscalator(ABC):
    """
    Abstract base class for all game escalators.
    Enforces that any escalator must provide blind parameters given the game context.
    """

    @abstractmethod
    def get_blind_parameters(self, hand_count: int, active_player_count: int):
        """
        Calculates the blind and ante config for the upcoming hand.

        Args:
            hand_count (int): The current hand count (starts at 0).
            active_player_count (int): How many players are currently 'alive'.

        Returns:
            tuple: (small_blind, big_blind, individual_ante, big_blind_ante)
        """
        pass


class NoLimitHoldemEscalator(BaseEscalator):
    def __init__(self, hands_per_level=10):
        self.hands_per_level = hands_per_level

        # Standard NLHE Tournament Levels (Turbo)
        # Recommended initial stack: 2000 - 3000 (100 BB - 150 BB)
        self.LEVELS = [
            # Deep Stack Phase
            {"sb": 10, "bb": 20, "ante": 0, "bba": 0},
            {"sb": 15, "bb": 30, "ante": 0, "bba": 0},
            {"sb": 20, "bb": 40, "ante": 0, "bba": 0},

            # Big Blind Ante Kicks In (Level 4)
            {"sb": 25, "bb": 50, "ante": 0, "bba": 50},
            {"sb": 50, "bb": 100, "ante": 0, "bba": 100},
            {"sb": 75, "bb": 150, "ante": 0, "bba": 150},
            {"sb": 100, "bb": 200, "ante": 0, "bba": 200},
            {"sb": 150, "bb": 300, "ante": 0, "bba": 300},
            {"sb": 200, "bb": 400, "ante": 0, "bba": 400},
            {"sb": 300, "bb": 600, "ante": 0, "bba": 600},
            {"sb": 400, "bb": 800, "ante": 0, "bba": 800},
            {"sb": 500, "bb": 1000, "ante": 0, "bba": 1000},
            {"sb": 1000, "bb": 2000, "ante": 0, "bba": 2000},
            {"sb": 1500, "bb": 3000, "ante": 0, "bba": 3000},
            {"sb": 3000, "bb": 6000, "ante": 0, "bba": 6000},
            {"sb": 5000, "bb": 10000, "ante": 0, "bba": 10000},
        ]

    def get_blind_parameters(self, hand_count: int, active_player_count: int):
        # Logic: Level depends purely on how many hands have been played
        if hand_count < 0: hand_count = 0

        level_index = hand_count // self.hands_per_level

        # Cap at max level
        if level_index >= len(self.LEVELS):
            level_index = len(self.LEVELS) - 1

        lvl = self.LEVELS[level_index]
        return lvl['sb'], lvl['bb'], lvl['ante'], lvl['bba']


class SurvivalEscalator(BaseEscalator):
    def __init__(self, total_starting_players):
        self.start_count = total_starting_players

        # We map "Players Remaining" to a specific blind level.
        # As players drop, the index increases.
        self.LEVELS = [
            {"sb": 50, "bb": 100, "ante": 0, "bba": 0},  # 9-10 players
            {"sb": 100, "bb": 200, "ante": 0, "bba": 200},  # 7-8 players
            {"sb": 200, "bb": 400, "ante": 0, "bba": 400},  # 5-6 players
            {"sb": 500, "bb": 1000, "ante": 0, "bba": 1000},  # 3-4 players
            {"sb": 1000, "bb": 2000, "ante": 0, "bba": 2000},  # Heads up (2 players)
        ]

    def get_blind_parameters(self, hand_count: int, active_player_count: int):
        # Logic: The fewer players alive, the higher the blinds.

        # Calculate how many players have died
        eliminated = self.start_count - active_player_count

        # Example logic: Increase level for every 2 players eliminated
        level_index = eliminated // 2

        # Cap at max level
        if level_index >= len(self.LEVELS):
            level_index = len(self.LEVELS) - 1

        lvl = self.LEVELS[level_index]
        return lvl['sb'], lvl['bb'], lvl['ante'], lvl['bba']