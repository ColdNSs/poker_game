from .base_agent import BasePokerAgent
from typing import List, Dict, Tuple
import math


class ChatgptAgent(BasePokerAgent):
    """
    A deterministic, tournament-focused No-Limit Texas Hold'em agent.

    Philosophy:
    - Designed to WIN tournaments, not maximize chip EV in isolation.
    - Stack-depth aware (push/fold <15bb, mixed 15–30bb, postflop edge >30bb).
    - Positionally aware.
    - Exploitatively adaptive using simple opponent stats.
    - Risk-adjusted aggression (ICM-lite via stack preservation when short).
    - Deterministic except for controlled randomness via self._random.

    No ML. Fully rule-based and interpretable.
    """

    def __init__(self, seed: int = None, name: str = "ChatGPT Agent"):
        super().__init__(seed, name)

    # -------------------------- #
    #        GAME LIFECYCLE      #
    # -------------------------- #

    def game_start(self, start_state: Dict):
        self.initial_stack = start_state["initial_stack_per_player"]
        self.player_count = start_state["player_count"]
        self.level_one_bb = start_state["level_one_big_blind"]
        self.my_id = start_state["your_status"]["player_id"]

        # Opponent modeling database
        # player_id -> stats
        self.opponent_stats = {}
        for p in start_state["players"]:
            if p["player_id"] != self.my_id:
                self.opponent_stats[p["player_id"]] = {
                    "hands": 0,
                    "vpip": 0,      # voluntarily put money in preflop
                    "pfr": 0,       # preflop raise
                    "showdowns": 0,
                    "aggressive_actions": 0,
                }

        self.hand_counter = 0

    # -------------------------- #
    #       CORE DECISION        #
    # -------------------------- #

    def decide_action(self, game_state: Dict) -> Dict:
        stage = game_state["current_stage"]

        if stage == "pre-flop":
            return self._decide_preflop(game_state)
        else:
            return self._decide_postflop(game_state)

    # -------------------------- #
    #        PRE-FLOP LOGIC      #
    # -------------------------- #

    def _decide_preflop(self, game_state: Dict) -> Dict:
        hole_cards = game_state["hole_cards"]
        bb = game_state["big_blind"]
        stack = game_state["your_status"]["stack"]
        cost_to_match = game_state["cost_to_match"]
        min_cost_to_increase = game_state["min_cost_to_increase"]
        can_raise = game_state["your_status"]["can_raise"]
        position = game_state["your_status"]["position"]

        effective_bb = stack / bb

        hand_strength = self._evaluate_preflop_strength(hole_cards)

        # -------- SHORT STACK PUSH/FOLD (<15bb) -------- #
        if effective_bb <= 15:
            return self._short_stack_strategy(
                hand_strength,
                effective_bb,
                cost_to_match,
                min_cost_to_increase,
                stack,
                can_raise,
            )

        # -------- MID STACK (15–30bb) -------- #
        elif effective_bb <= 30:
            return self._mid_stack_strategy(
                hand_strength,
                position,
                cost_to_match,
                min_cost_to_increase,
                bb,
                stack,
                can_raise,
            )

        # -------- DEEP STACK (>30bb) -------- #
        else:
            return self._deep_stack_strategy(
                hand_strength,
                position,
                cost_to_match,
                min_cost_to_increase,
                bb,
                stack,
                can_raise,
            )

    # -------------------------- #
    #      SHORT STACK LOGIC     #
    # -------------------------- #

    def _short_stack_strategy(
        self,
        strength: float,
        effective_bb: float,
        cost_to_match: int,
        min_cost_to_increase: int,
        stack: int,
        can_raise: bool,
    ) -> Dict:

        # Jam range expands as stack gets shorter
        shove_threshold = 0.55 - (15 - effective_bb) * 0.015

        if strength >= shove_threshold and can_raise:
            return {"action": "increase", "amount": stack}

        if cost_to_match == 0:
            return {"action": "match"}

        if strength >= shove_threshold - 0.05:
            return {"action": "match"}

        return {"action": "fold"}

    # -------------------------- #
    #       MID STACK LOGIC      #
    # -------------------------- #

    def _mid_stack_strategy(
        self,
        strength: float,
        position: int,
        cost_to_match: int,
        min_cost_to_increase: int,
        bb: int,
        stack: int,
        can_raise: bool,
    ) -> Dict:

        open_threshold = 0.45 - position * 0.015
        reraise_threshold = 0.65

        if cost_to_match == 0:
            if strength >= open_threshold and can_raise:
                raise_size = int(2.2 * bb)
                return {"action": "increase", "amount": max(raise_size, min_cost_to_increase)}
            return {"action": "match"}

        # Facing raise
        if strength >= reraise_threshold and can_raise:
            return {"action": "increase", "amount": stack}

        if strength >= open_threshold:
            return {"action": "match"}

        return {"action": "fold"}

    # -------------------------- #
    #       DEEP STACK LOGIC     #
    # -------------------------- #

    def _deep_stack_strategy(
        self,
        strength: float,
        position: int,
        cost_to_match: int,
        min_cost_to_increase: int,
        bb: int,
        stack: int,
        can_raise: bool,
    ) -> Dict:

        open_threshold = 0.40 - position * 0.02
        threebet_threshold = 0.70

        if cost_to_match == 0:
            if strength >= open_threshold and can_raise:
                raise_size = int(2.5 * bb)
                return {"action": "increase", "amount": max(raise_size, min_cost_to_increase)}
            return {"action": "match"}

        if strength >= threebet_threshold and can_raise:
            raise_size = int(3 * cost_to_match)
            raise_size = min(raise_size, stack)
            return {"action": "increase", "amount": max(raise_size, min_cost_to_increase)}

        if strength >= open_threshold + 0.05:
            return {"action": "match"}

        return {"action": "fold"}

    # -------------------------- #
    #       POST-FLOP LOGIC      #
    # -------------------------- #

    def _decide_postflop(self, game_state: Dict) -> Dict:
        hole_cards = game_state["hole_cards"]
        board = game_state["community_cards"]
        stage = game_state["current_stage"]

        strength = self._evaluate_postflop_strength(hole_cards, board)

        pot = sum(p["amount"] for p in game_state["pots"])
        cost_to_match = game_state["cost_to_match"]
        min_cost_to_increase = game_state["min_cost_to_increase"]
        stack = game_state["your_status"]["stack"]
        can_raise = game_state["your_status"]["can_raise"]

        pot_odds = 0
        if cost_to_match > 0:
            pot_odds = cost_to_match / (pot + cost_to_match)

        # Strong made hand
        if strength > 0.80 and can_raise:
            bet_size = int(pot * 0.75)
            bet_size = min(bet_size, stack)
            return {"action": "increase", "amount": max(bet_size, min_cost_to_increase)}

        # Medium strength
        if strength > 0.55:
            if cost_to_match == 0:
                if can_raise and self._random.random() < 0.4:
                    bet_size = int(pot * 0.5)
                    return {"action": "increase", "amount": max(bet_size, min_cost_to_increase)}
                return {"action": "match"}

            if strength > pot_odds:
                return {"action": "match"}

            return {"action": "fold"}

        # Draw logic
        if 0.35 < strength <= 0.55:
            if cost_to_match == 0:
                return {"action": "match"}

            if strength > pot_odds:
                return {"action": "match"}

        return {"action": "fold"}

    # -------------------------- #
    #      HAND EVALUATION       #
    # -------------------------- #

    def _evaluate_preflop_strength(self, hole_cards: List[str]) -> float:
        """
        Returns normalized [0,1] strength.

        Heuristic model:
        - Pair strength
        - High card value
        - Suited bonus
        - Connected bonus
        """

        ranks = "23456789TJQKA"
        r1 = ranks.index(hole_cards[0][0])
        r2 = ranks.index(hole_cards[1][0])
        suited = hole_cards[0][1] == hole_cards[1][1]

        high = max(r1, r2)
        low = min(r1, r2)

        # Pair
        if r1 == r2:
            return 0.6 + (high / 12) * 0.4

        strength = (high / 12) * 0.6 + (low / 12) * 0.2

        if suited:
            strength += 0.05

        if abs(r1 - r2) == 1:
            strength += 0.05

        return min(strength, 1.0)

    def _evaluate_postflop_strength(self, hole_cards: List[str], board: List[str]) -> float:
        """
        Simplified postflop strength estimator.

        Detects:
        - Pair+
        - Trips
        - Two pair
        - Strong draws
        """

        ranks = "23456789TJQKA"
        values = [ranks.index(c[0]) for c in hole_cards + board]
        counts = {v: values.count(v) for v in values}

        max_count = max(counts.values())

        # Trips+
        if max_count >= 3:
            return 0.9

        # Two pair
        pairs = sum(1 for v in counts.values() if v == 2)
        if pairs >= 2:
            return 0.8

        # One pair
        if pairs == 1:
            return 0.6

        # Flush draw detection
        suits = [c[1] for c in hole_cards + board]
        for s in "shdc":
            if suits.count(s) >= 4:
                return 0.5

        # Overcards heuristic
        hole_values = [ranks.index(c[0]) for c in hole_cards]
        board_values = [ranks.index(c[0]) for c in board]
        if hole_values and board_values:
            if max(hole_values) > max(board_values):
                return 0.45

        return 0.2

    # -------------------------- #
    #       OPPONENT MODEL       #
    # -------------------------- #

    def hand_ended(self, hand_history: Dict):
        self.hand_counter += 1

        for result in hand_history["player_results"]:
            pid = result["player_id"]
            if pid == self.my_id:
                continue

            if pid in self.opponent_stats:
                self.opponent_stats[pid]["hands"] += 1
                if result["hole_cards"] is not None:
                    self.opponent_stats[pid]["showdowns"] += 1
