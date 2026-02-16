import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from .base_agent import BasePokerAgent

# --- Constants & Configuration ---

RANK_MAP = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
}
SUIT_MAP = {'h': 0, 'd': 1, 'c': 2, 's': 3}  # Hearts, Diamonds, Clubs, Spades

# Hand Strength Categories (Higher is better)
HS_HIGH_CARD = 0
HS_PAIR = 1
HS_TWO_PAIR = 2
HS_TRIPS = 3
HS_STRAIGHT = 4
HS_FLUSH = 5
HS_FULL_HOUSE = 6
HS_QUADS = 7
HS_STRAIGHT_FLUSH = 8
HS_ROYAL_FLUSH = 9


# --- Utility Structures ---

@dataclass
class Card:
    rank_char: str
    suit_char: str
    rank: int
    suit: int

    @staticmethod
    def from_str(card_str: str) -> 'Card':
        return Card(
            rank_char=card_str[0],
            suit_char=card_str[1],
            rank=RANK_MAP[card_str[0]],
            suit=SUIT_MAP[card_str[1]]
        )

    def __repr__(self):
        return f"{self.rank_char}{self.suit_char}"


@dataclass
class EvaluatedHand:
    category: int
    score: float  # Absolute strength score for comparison
    description: str
    draw_potential: float = 0.0  # 0.0 to 1.0 representing flush/straight draws


@dataclass
class OpponentStats:
    hands_seen: int = 0
    vpip_count: int = 0
    pfr_count: int = 0
    showdown_hands: List[str] = field(default_factory=list)

    @property
    def vpip(self) -> float:
        return self.vpip_count / max(1, self.hands_seen)

    @property
    def pfr(self) -> float:
        return self.pfr_count / max(1, self.hands_seen)

    @property
    def style(self) -> str:
        if self.hands_seen < 10: return "unknown"
        if self.vpip > 0.40: return "loose"
        if self.vpip < 0.15: return "tight"
        return "normal"


# --- Strategy Implementation ---

class GeminiAgent(BasePokerAgent):
    """
    A professional-grade Tournament Poker Agent.

    Key Strategies:
    1. Stack Depth Awareness: Adjusts ranges based on M-ratio and Effective Big Blinds (BB).
    2. Position Awareness: Wider ranges in Late Position (LP), tighter in Early Position (EP).
    3. Hand Evaluation: Custom heuristic evaluator for Made Hands and Draws.
    4. Opponent Modeling: Tracks VPIP/PFR to identify Tight/Loose opponents.
    5. Pot Odds & Expected Value: Mathematical approach to calling/folding.
    6. Randomization: Uses seed-based randomness to mix play in marginal spots.
    """

    def __init__(self, seed: int = None, name: str = "Gemini Agent"):
        super().__init__(seed, name)

    def game_start(self, start_state):
        self.opponent_stats: Dict[int, OpponentStats] = defaultdict(OpponentStats)
        self.my_player_id = start_state['your_status']['player_id']
        # Database of actions this game to avoid double counting stats
        self.processed_hand_ids = set()

    def decide_action(self, game_state):
        try:
            # 1. Parse State
            self.gs = game_state
            self.my_id = self.gs['your_status']['player_id']
            self.hole_cards = [Card.from_str(c) for c in self.gs['hole_cards']]
            self.community_cards = [Card.from_str(c) for c in self.gs['community_cards']]
            self.stage = self.gs['current_stage']

            # Betting Constants
            self.bb = self.gs['big_blind']
            self.sb = self.gs['small_blind']
            self.ante = self.gs['ante']
            self.cost_to_match = self.gs['cost_to_match']
            self.min_raise_cost = self.gs['min_cost_to_increase']
            self.stack = self.gs['your_status']['stack']
            self.pot = self.gs['pots'][0]['amount']  # Main pot focus

            # Context
            self.active_players = [p for p in self.gs['players'] if p['hand_status'] == 'active']
            self.num_active = len(self.active_players)
            self.position_category = self._get_position_category()

            # Stack Metrics
            pot_bloat = sum(p['total_bet_this_hand'] for p in self.gs['players'])
            total_pot = self.pot + pot_bloat  # Approximation of total chips in middle
            self.stack_in_bb = self.stack / self.bb
            self.m_ratio = self.stack / (self.bb + self.sb + (self.ante * len(self.gs['players'])))

            # 2. Decision Logic Routing
            if self.stage == 'pre-flop':
                return self._play_preflop()
            else:
                return self._play_postflop()

        except Exception as e:
            # Failsafe: Check/Fold to avoid crashing the tournament
            return self._action_fold_or_check()

    def hand_ended(self, hand_history):
        """Analyze showdowns and actions to update opponent stats."""
        hand_id = hand_history['hand_id']
        if hand_id in self.processed_hand_ids:
            return
        self.processed_hand_ids.add(hand_id)

        # Parse log for VPIP/PFR
        player_actions = defaultdict(list)
        for log in hand_history['hand_log']:
            if log['stage'] == 'pre-flop':
                player_actions[log['player_id']].append(log['action'])

        for p_res in hand_history['player_results']:
            pid = p_res['player_id']
            if pid == self.my_player_id:
                continue  # Don't track self

            stats = self.opponent_stats[pid]
            stats.hands_seen += 1

            actions = player_actions[pid]
            # VPIP: Voluntarily put chips in (call, bet, raise) not including blinds check
            if any(a in ['call', 'bet', 'raise', 'all-in'] for a in actions):
                stats.vpip_count += 1
            # PFR: Raised pre-flop
            if any(a in ['raise', 'all-in'] for a in actions):  # basic PFR detection
                stats.pfr_count += 1

    # --- Pre-Flop Strategy ---

    def _play_preflop(self):
        card1, card2 = sorted(self.hole_cards, key=lambda c: c.rank, reverse=True)
        is_pair = card1.rank == card2.rank
        is_suited = card1.suit == card2.suit

        # Tier Definition
        tier = self._get_hand_tier(card1, card2, is_pair, is_suited)

        # Scenario 1: Short Stack (Push/Fold)
        if self.m_ratio < 6 or self.stack_in_bb < 12:
            return self._play_push_fold(tier)

        # Scenario 2: Deep Stack / Normal Play
        current_bet = self.gs['your_status']['current_bet_this_stage']

        # A. Unopened Pot (We are first to enter or everyone folded)
        is_unopened = self.cost_to_match == 0 or (self.cost_to_match <= self.bb and current_bet < self.bb)

        if is_unopened:
            return self._open_pot_logic(tier)

        # B. Facing Action
        return self._facing_action_preflop(tier)

    def _get_hand_tier(self, c1, c2, pair, suited) -> int:
        """Returns 1 (Best) to 8 (Trash)."""
        r1, r2 = c1.rank, c2.rank

        if pair:
            if r1 >= 10: return 1  # AA, KK, QQ, JJ, TT
            if r1 >= 7: return 2  # 99, 88, 77
            if r1 >= 5: return 3  # 66, 55
            return 4  # 44, 33, 22

        if suited:
            if r1 == 14 and r2 >= 10: return 1  # AKs, AQs, AJs, ATs
            if r1 == 13 and r2 >= 11: return 2  # KQs, KJs
            if r1 == 14: return 3  # A9s-A2s
            if r1 >= 10 and r2 >= 10: return 3  # QJs, JTs etc
            if r1 - r2 == 1 and r1 >= 5: return 4  # Connectors 54s+
            if r1 - r2 == 2 and r1 >= 7: return 5  # Gappers
            return 6

        # Offsuit
        if r1 == 14 and r2 >= 11: return 1  # AKo, AQo, AJo
        if r1 == 13 and r2 >= 12: return 2  # KQo
        if r1 == 14 and r2 >= 10: return 3  # ATo
        if r1 >= 11 and r2 >= 10: return 5  # QJo, JTo

        return 8  # Trash

    def _open_pot_logic(self, tier):
        """Decide to open raise or fold."""
        # Positions: 0=SB, 1=BB (Wait, API says Dealer is 0. So logic: 0=BTN, 1=SB, 2=BB in 3-handed?)
        # Let's rely on self.position_category mapping.

        # Logic: raise top X% based on position
        playable_tier = 4  # Default

        if self.position_category == 'EP':
            playable_tier = 2
        elif self.position_category == 'MP':
            playable_tier = 3
        elif self.position_category == 'LP':
            playable_tier = 5
        elif self.position_category == 'SB':
            playable_tier = 6  # Steal wide

        if tier <= playable_tier:
            # Raise size: 2.2bb to 3bb usually
            amt = int(self.bb * (2.2 + (0.5 if self.position_category == 'SB' else 0)))
            return self._action_raise(amt)

        return self._action_fold_or_check()

    def _facing_action_preflop(self, tier):
        """Facing a raise, call, or 3-bet."""
        pot_odds = self.cost_to_match / (self.pot + self.cost_to_match + 1)

        # 3-bet Logic (Premium hands)
        if tier == 1:
            # Reraise roughly 3x the cost
            return self._action_raise(self.cost_to_match * 3)

        # Call Logic (Set mining, Suited connectors, Strong high cards)
        # If cost is low relative to stack (Implied odds)
        can_call_profitably = False

        if tier <= 2: can_call_profitably = True

        # Set Mining (Pairs) - Call if we have 15x behind
        is_pair = self.hole_cards[0].rank == self.hole_cards[1].rank
        if is_pair and tier <= 4:
            if self.stack > self.cost_to_match * 12:
                can_call_profitably = True

        # Suited Connectors / Suited Aces (Tier 3-4 suited) - Call if deep & cheap
        is_suited = self.hole_cards[0].suit == self.hole_cards[1].suit
        if is_suited and tier <= 4 and self.position_category in ['LP', 'BB']:
            if self.stack > self.cost_to_match * 20:
                can_call_profitably = True

        # Big Blind Defense
        if self.position_category == 'BB' and tier <= 6 and pot_odds < 0.35:
            # Defend wide in BB against small opens
            can_call_profitably = True

        if can_call_profitably:
            return self._action_call()

        return self._action_fold_or_check()

    def _play_push_fold(self, tier):
        """Nash-equilibrium inspired short stack logic."""
        # Simplified Push/Fold charts
        push = False

        # Super short (< 6 BB) - Push any pair, any Ax, any broadway, suited connectors
        if self.stack_in_bb < 6:
            if tier <= 6: push = True
        # Short (6-12 BB)
        else:
            if self.position_category in ['LP', 'SB']:
                if tier <= 5: push = True
            else:
                if tier <= 2: push = True  # Tight in EP

        if push:
            return self._action_all_in()
        else:
            return self._action_fold_or_check()

    # --- Post-Flop Strategy ---

    def _play_postflop(self):
        evaluation = self._evaluate_hand(self.hole_cards, self.community_cards)
        hand_strength = evaluation.score  # 0.0 to 1.0 (relative)

        # Determine current effective pot odds
        total_pot = sum(p['amount'] for p in self.gs['pots']) + sum(
            p['total_bet_this_hand'] for p in self.gs['players'])
        if self.cost_to_match > 0:
            pot_odds = self.cost_to_match / (total_pot + self.cost_to_match)
        else:
            pot_odds = 0

        # 1. Monster Hands (Sets, Straights, Flushes) -> Build Pot
        if evaluation.category >= HS_STRAIGHT or (evaluation.category == HS_TRIPS and evaluation.score > 0.8):
            return self._play_monster(evaluation)

        # 2. Strong Hands (Top Pair Top Kicker, Overpair) -> Value Bet / Call
        if evaluation.category == HS_TWO_PAIR or (evaluation.category == HS_PAIR and evaluation.score > 0.85):
            return self._play_strong(evaluation)

        # 3. Draws (Flush Draw, Straight Draw) -> Semi-bluff or Call with odds
        if evaluation.draw_potential > 0:
            return self._play_draw(evaluation, pot_odds)

        # 4. Marginal/Air -> Bluff catch or Fold
        return self._play_marginal(evaluation, pot_odds)

    def _play_monster(self, eval_hand):
        # Slow play on dry boards if huge favorite?
        # Generally in tournaments, fast play is safer to avoid bad beats.
        if self.cost_to_match > 0:
            # Raise for value
            return self._action_raise_pot_percentage(0.75)
        else:
            # Bet
            return self._action_bet_pot_percentage(0.66)

    def _play_strong(self, eval_hand):
        if self.cost_to_match > 0:
            # Check if raise is too big (committed logic)
            if self.cost_to_match > self.stack * 0.4:
                # Commit
                return self._action_call()
            else:
                return self._action_call()
        else:
            # Bet for value/protection
            return self._action_bet_pot_percentage(0.50)

    def _play_draw(self, eval_hand, pot_odds):
        outs = 0
        # Estimate outs based on draw potential flag
        if eval_hand.draw_potential >= 0.9:
            outs = 9  # Flush draw
        elif eval_hand.draw_potential >= 0.8:
            outs = 8  # OESD
        elif eval_hand.draw_potential >= 0.4:
            outs = 4  # Gutshot

        cards_to_come = 0
        if self.stage == 'flop':
            cards_to_come = 2
        elif self.stage == 'turn':
            cards_to_come = 1

        equity = (outs * cards_to_come * 2) / 100.0  # Rule of 2/4

        # Aggressive Semi-Bluff? (Mix it up)
        do_bluff = self._random.random() < 0.20  # 20% frequency

        if self.cost_to_match == 0:
            if do_bluff and self.position_category == 'LP':
                return self._action_bet_pot_percentage(0.5)
            return self._action_check()

        if equity >= pot_odds:
            return self._action_call()

        # Implied odds adjustment: if we hit, we stack them?
        if self.stack > self.cost_to_match * 10 and equity > pot_odds * 0.7:
            return self._action_call()

        return self._action_fold_or_check()

    def _play_marginal(self, eval_hand, pot_odds):
        # C-Bet Bluff logic
        # If we were the aggressor pre-flop, we have "range advantage"
        am_aggressor = self.gs['your_status']['current_bet_this_stage'] > 0  # Simplified check

        # Check fold
        if self.cost_to_match > 0:
            # Hero call?
            # Only if opponent is loose and bet is small
            return self._action_fold_or_check()

        # We can check or bluff bet
        if self.stage == 'flop':
            # C-Bet frequency on dry boards
            if self._random.random() < 0.4:
                return self._action_bet_pot_percentage(0.33)

        return self._action_check()

    # --- Actions Helpers ---

    def _action_fold_or_check(self):
        if self.cost_to_match == 0:
            return {"action": "match"}
        return {"action": "fold"}

    def _action_raise(self, amount: int):
        """
        Safety wrapper to ensure raises are legal.
        """
        # 1. Must be at least min_increase + current_bet or min_cost_to_increase
        # The API says: "The amount should be at least `min_cost_to_increase`."
        # The API also says: "When you choose to increase, you MUST provide the amount you want to SPEND"

        target_amount = int(amount)
        min_cost = self.gs['min_cost_to_increase']

        if target_amount < min_cost:
            target_amount = min_cost

        # 2. Cannot exceed stack
        if target_amount >= self.stack:
            return self._action_all_in()

        return {
            "action": "increase",
            "amount": target_amount
        }

    def _action_call(self):
        """Calls or Checks depending on cost."""
        return {"action": "match"}  # API handles amount automatically

    def _action_check(self):
        """Explicit check (only valid if cost_to_match is 0)."""
        if self.cost_to_match > 0:
            return self._action_fold_or_check()
        return {"action": "match"}

    def _action_all_in(self):
        return {
            "action": "increase",
            "amount": self.stack
        }

    def _action_bet_pot_percentage(self, pct):
        total_pot = sum(p['amount'] for p in self.gs['pots'])
        bet_amt = int(total_pot * pct)
        if bet_amt < self.bb: bet_amt = self.bb
        return self._action_raise(bet_amt)

    def _action_raise_pot_percentage(self, pct):
        total_pot = sum(p['amount'] for p in self.gs['pots'])
        # Raise size logic: (Pot + Call) * pct + Call
        raise_amt = int((total_pot + self.cost_to_match) * pct) + self.cost_to_match
        return self._action_raise(raise_amt)

    # --- Position & Utilities ---

    def _get_position_category(self):
        # Determine position based on dealer button
        # API says: "Game plays clockwise 0 -> 1 -> ...". Dealer is at position 0 in the list?
        # No, 'your_status' has 'position'. "Dealer is always at 0".

        pos = self.gs['your_status']['position']
        total = len(self.gs['players'])

        if total == 2:
            return 'SB' if pos == 0 else 'BB'  # Heads up: Dealer is SB

        # 6-max or 9-max approximation
        if pos == 0: return 'BTN'  # Dealer/LP
        if pos == 1: return 'SB'
        if pos == 2: return 'BB'

        # UTG
        if pos == 3: return 'EP'

        # Remaining
        if total - pos <= 2: return 'LP'  # Cutoff / Hijack
        return 'MP'

    # --- Heuristic Hand Evaluator ---

    def _evaluate_hand(self, hole: List[Card], comm: List[Card]) -> EvaluatedHand:
        """
        Determines the current strength of the hand and its draw potential.
        Returns an EvaluatedHand object used by the strategy engine.
        """
        all_cards = hole + comm
        if not all_cards:
            return EvaluatedHand(HS_HIGH_CARD, 0, "Empty")

        # Sort by rank descending
        all_cards.sort(key=lambda c: c.rank, reverse=True)
        ranks = [c.rank for c in all_cards]
        suits = [c.suit for c in all_cards]
        rank_counts = Counter(ranks)
        suit_counts = Counter(suits)

        # --- Hand Category Determination ---

        # 1. Straight Flush / Royal Flush checks
        flush_suit = None
        for s, count in suit_counts.items():
            if count >= 5:
                flush_suit = s
                break

        straight_high_card = self._get_straight_high_card(list(set(ranks)))

        if flush_suit is not None:
            # Filter cards of the flush suit
            flush_cards_ranks = sorted([c.rank for c in all_cards if c.suit == flush_suit], reverse=True)
            sf_high = self._get_straight_high_card(flush_cards_ranks)

            if sf_high:
                if sf_high == 14:
                    return EvaluatedHand(HS_ROYAL_FLUSH, 1.0, "Royal Flush")
                return EvaluatedHand(HS_STRAIGHT_FLUSH, 0.9 + (sf_high / 100), "Straight Flush")

        # 2. Quads
        if 4 in rank_counts.values():
            quad_rank = max(r for r, c in rank_counts.items() if c == 4)
            return EvaluatedHand(HS_QUADS, 0.9 + (quad_rank / 100), "Quads")

        # 3. Full House
        trips = [r for r, c in rank_counts.items() if c >= 3]
        pairs = [r for r, c in rank_counts.items() if c >= 2]
        if trips:
            top_trip = max(trips)
            # Find a pair that isn't the same rank as the trip (or a second trip)
            remaining_pairs = [p for p in pairs if p != top_trip]
            if remaining_pairs:
                top_pair = max(remaining_pairs)
                score = 0.8 + (top_trip * 0.01) + (top_pair * 0.0001)
                return EvaluatedHand(HS_FULL_HOUSE, score, "Full House")

        # 4. Flush
        if flush_suit is not None:
            flush_ranks = sorted([c.rank for c in all_cards if c.suit == flush_suit], reverse=True)
            top_flush_card = flush_ranks[0]
            return EvaluatedHand(HS_FLUSH, 0.7 + (top_flush_card / 100), "Flush")

        # 5. Straight
        if straight_high_card:
            return EvaluatedHand(HS_STRAIGHT, 0.6 + (straight_high_card / 100), "Straight")

        # 6. Trips
        if trips:
            top_trip = max(trips)
            return EvaluatedHand(HS_TRIPS, 0.5 + (top_trip / 100), "Trips")

        # 7. Two Pair
        if len(pairs) >= 2:
            pairs.sort(reverse=True)
            score = 0.4 + (pairs[0] * 0.01) + (pairs[1] * 0.0001)
            return EvaluatedHand(HS_TWO_PAIR, score, "Two Pair")

        # 8. Pair
        if pairs:
            top_pair = max(pairs)
            # Check if Top Pair
            board_high = max([c.rank for c in comm]) if comm else 0
            is_top_pair = top_pair >= board_high
            base_val = 0.3 if is_top_pair else 0.2

            # Check kicker strength
            kickers = [r for r in ranks if r != top_pair]
            kicker_val = kickers[0] / 1000 if kickers else 0

            # Calculate Draw Potential for semi-bluffing opportunities
            draw_pot = self._calculate_draw_potential(ranks, suit_counts)

            return EvaluatedHand(HS_PAIR, base_val + (top_pair / 100) + kicker_val, "Pair", draw_potential=draw_pot)

        # 9. High Card
        top_card = ranks[0]
        draw_pot = self._calculate_draw_potential(ranks, suit_counts)
        return EvaluatedHand(HS_HIGH_CARD, top_card / 100, "High Card", draw_potential=draw_pot)

    def _get_straight_high_card(self, unique_ranks: List[int]) -> Optional[int]:
        """Helper to find the highest card of a straight."""
        if len(unique_ranks) < 5:
            return None

        # Check standard straights
        for i in range(len(unique_ranks) - 4):
            window = unique_ranks[i:i + 5]
            if window[0] - window[4] == 4:
                return window[0]

        # Check Wheel (A-5 straight)
        # unique_ranks is sorted desc, so A is at 0 if present
        if 14 in unique_ranks and {5, 4, 3, 2}.issubset(set(unique_ranks)):
            return 5

        return None

    def _calculate_draw_potential(self, ranks: List[int], suit_counts: Counter) -> float:
        """
        Calculates a 0.0 to 1.0 score for draw strength.
        1.0 ~= Monster Draw, 0.9 = Flush Draw, 0.8 = OESD, 0.4 = Gutshot
        """
        potential = 0.0

        # Flush Draw (4 cards of same suit)
        if any(c == 4 for c in suit_counts.values()):
            potential = 0.9

        # Straight Draw logic
        unique_ranks = sorted(list(set(ranks)), reverse=True)

        # Open Ended Straight Draw (OESD): 4 consecutive cards
        has_oesd = False
        for i in range(len(unique_ranks) - 3):
            window = unique_ranks[i:i + 4]
            if window[0] - window[3] == 3:
                has_oesd = True
                break

        if has_oesd:
            potential = max(potential, 0.8)

        # Gutshot: 4 cards within a span of 5
        has_gutshot = False
        if not has_oesd:
            for i in range(len(unique_ranks) - 3):
                window = unique_ranks[i:i + 4]
                if window[0] - window[3] == 4:  # Gap of 1 inside
                    has_gutshot = True
                    break
            # Wheel gutshot check
            if 14 in unique_ranks and len({5, 4, 3, 2} & set(unique_ranks)) == 3:
                has_gutshot = True

        if has_gutshot:
            potential = max(potential, 0.4)

        return potential