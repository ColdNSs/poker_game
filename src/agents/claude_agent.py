"""
Tournament No-Limit Texas Hold'em Agent
A rule-based, fully interpretable tournament poker bot.

Strategy pillars:
  1. Preflop: Chen-scored hand tiers × position × M-ratio
  2. Postflop: Hand rank + draw equity × pot-odds × position × board texture
  3. Tournament dynamics: Push/fold when M < 10, survival logic, ICM awareness
  4. Opponent modelling: VPIP / PFR / aggression-factor tracked hand-over-hand
  5. Exploitative adjustments: punish tight, defend against aggression
"""

from .base_agent import BasePokerAgent
from collections import Counter, defaultdict
from itertools import combinations
from typing import List, Tuple, Optional, Dict, Any
import math

# ─── Card primitives ──────────────────────────────────────────────────────────
RANKS  = '23456789TJQKA'
RANK_VAL = {r: i for i, r in enumerate(RANKS)}   # '2'=0 … 'A'=12

def _rank(c: str) -> int: return RANK_VAL[c[0]]
def _suit(c: str) -> str: return c[1]


# ─── 5-card hand evaluator ────────────────────────────────────────────────────
def _score5(cards: List[str]) -> tuple:
    """
    Return a comparable tuple for a 5-card hand.
    Higher tuple == stronger hand.
    (8) = straight-flush … (0) = high-card
    """
    ranks  = sorted([_rank(c) for c in cards], reverse=True)
    suits  = [_suit(c) for c in cards]
    flush  = len(set(suits)) == 1

    cnt    = Counter(ranks)
    groups = sorted(cnt.items(), key=lambda x: (x[1], x[0]), reverse=True)
    g_cnt  = [g[1] for g in groups]
    g_rnk  = [g[0] for g in groups]

    # Straight detection
    straight, s_high = False, 0
    if len(cnt) == 5:
        if ranks[0] - ranks[4] == 4:
            straight, s_high = True, ranks[0]
        elif set(ranks) == {12, 3, 2, 1, 0}:     # A-2-3-4-5 wheel
            straight, s_high = True, 3

    if straight and flush:              return (8, s_high)
    if g_cnt[0] == 4:                   return (7, g_rnk[0], g_rnk[1])
    if g_cnt[0] == 3 and g_cnt[1] == 2: return (6, g_rnk[0], g_rnk[1])
    if flush:                           return (5,) + tuple(ranks)
    if straight:                        return (4, s_high)
    if g_cnt[0] == 3:                   return (3, g_rnk[0], g_rnk[1], g_rnk[2])
    if g_cnt[0] == 2 and g_cnt[1] == 2: return (2, g_rnk[0], g_rnk[1], g_rnk[2])
    if g_cnt[0] == 2:                   return (1, g_rnk[0]) + tuple(g_rnk[1:])
    return (0,) + tuple(ranks)


def best_hand_rank(hole: List[str], board: List[str]) -> Optional[tuple]:
    """Best 5-card hand score from hole + board cards."""
    all_cards = hole + board
    if len(all_cards) < 5:
        return None
    return max(_score5(list(f)) for f in combinations(all_cards, 5))


# ─── Preflop strength (Chen formula) ─────────────────────────────────────────
_CHEN_HIGH = {
    12: 10, 11: 8, 10: 7, 9: 6, 8: 5,
    7: 4, 6: 3.5, 5: 3, 4: 2.5, 3: 2, 2: 1.5, 1: 1, 0: 1
}

def preflop_strength(hole: List[str]) -> float:
    """
    Chen-formula score for two hole cards.
    Approximate ranges:
      >= 20 : AA
      >= 16 : KK
      >= 14 : QQ
      >= 12 : JJ, AKs
      >= 10 : TT, AKo, AQs
      >=  9 : 99, AJs, AQo, KQs
      >=  7 : 88, KJs, AJo, KQo
      >=  5 : 77–22, suited connectors, broadways
    """
    r1, r2 = _rank(hole[0]), _rank(hole[1])
    suited = _suit(hole[0]) == _suit(hole[1])
    hi, lo = max(r1, r2), min(r1, r2)

    if r1 == r2:
        return max(_CHEN_HIGH[hi] * 2, 5)

    score = _CHEN_HIGH[hi]
    if suited:
        score += 2
    gap = hi - lo - 1
    if gap == 0:
        score += 1
    elif gap == 1:
        pass          # no penalty
    elif gap == 2:
        score -= 1
    elif gap == 3:
        score -= 2
    else:
        score -= 4
    # bonus for connectedness potential on very low boards
    if hi < 12 and gap == 0 and lo >= 4:
        score += 0.5  # small additional playability bonus
    return score


# ─── Draw detection ───────────────────────────────────────────────────────────
def detect_draws(hole: List[str], board: List[str]) -> Dict[str, bool]:
    """
    Detect flush draw, open-ended straight draw, and gutshot
    in the combined hole + board cards.
    """
    if len(board) < 3:
        return {"fd": False, "oesd": False, "gs": False}

    all_cards  = hole + board
    suit_cnt   = Counter(_suit(c) for c in all_cards)
    rank_set   = set(_rank(c) for c in all_cards)

    # Flush draw: exactly 4 of a suit (5 = already made)
    fd = any(v == 4 for v in suit_cnt.values())

    # Straight draws: scan all possible 5-rank windows
    oesd = False
    gs   = False
    for low in range(0, 10):           # 2-low through T-low straights
        window = set(range(low, low + 5))
        have   = rank_set & window
        miss   = window - rank_set
        if len(have) == 4 and len(miss) == 1:
            m = next(iter(miss))
            if m == low or m == low + 4:
                oesd = True            # open-ended: missing an end card
            else:
                gs   = True            # gutshot: missing a middle card
    # Ace-low (wheel) gutshot
    wheel = {12, 0, 1, 2, 3}
    have_w = rank_set & wheel
    miss_w = wheel - rank_set
    if len(have_w) == 4 and len(miss_w) == 1:
        gs = True

    return {"fd": fd, "oesd": oesd, "gs": gs}


# ─── Board texture ────────────────────────────────────────────────────────────
def board_wetness(board: List[str]) -> int:
    """
    Rough wetness score (0 = very dry, higher = many draws present).
    Used to adjust postflop caution.
    """
    if len(board) < 3:
        return 0
    suits = [_suit(c) for c in board]
    ranks = sorted([_rank(c) for c in board])
    wet   = 0

    suit_cnt = Counter(suits)
    if max(suit_cnt.values()) >= 2: wet += 1
    if max(suit_cnt.values()) >= 3: wet += 3   # monotone board is very wet

    gaps = [ranks[i+1] - ranks[i] for i in range(len(ranks) - 1)]
    if min(gaps) == 1: wet += 2    # at least two connected board cards
    elif min(gaps) == 2: wet += 1

    return wet


# ─── Opponent model ───────────────────────────────────────────────────────────
class OpponentModel:
    """Per-opponent statistics accumulated over hands played."""
    def __init__(self, pid: int):
        self.player_id = pid
        self.hands_seen     = 0
        self.vpip           = 0   # Voluntarily Put In Pot preflop
        self.pfr            = 0   # Pre-Flop Raise
        self.agg_bets       = 0   # Aggressive actions (bet/raise)
        self.agg_calls      = 0   # Passive actions (call)
        self.showdowns      = 0
        self.showdown_wins  = 0

    @property
    def vpip_rate(self) -> float:
        return self.vpip / max(self.hands_seen, 1)

    @property
    def pfr_rate(self) -> float:
        return self.pfr / max(self.hands_seen, 1)

    @property
    def aggression_factor(self) -> float:
        """AF = bets+raises / calls. >2 = aggressive, <1 = passive."""
        return self.agg_bets / max(self.agg_calls, 1)

    def is_tight(self) -> bool:   return self.vpip_rate < 0.25
    def is_loose(self) -> bool:   return self.vpip_rate > 0.45
    def is_passive(self) -> bool: return self.aggression_factor < 1.2

    def limp_fest(self) -> bool:
        """Plays lots of hands but doesn't raise (limper)."""
        return self.is_loose() and self.pfr_rate < 0.10


# ─── Main agent ───────────────────────────────────────────────────────────────
class ClaudeAgent(BasePokerAgent):
    """
    Tournament NL Hold'em agent.
    Designed to adapt early/mid/late stage and exploit common opponent archetypes.
    """

    def __init__(self, seed: int = None, name: str = "Claude Agent"):
        super().__init__(seed, name)
        self.my_id: Optional[int]          = None
        self.opponents: Dict[int, OpponentModel] = {}
        self.initial_stack: int            = 2000
        self.player_count: int             = 8
        self.level_one_bb: int             = 20

    # ── Lifecycle hooks ────────────────────────────────────────────────────────
    def game_start(self, start_state: dict):
        self.my_id         = start_state["your_status"]["player_id"]
        self.initial_stack = start_state["initial_stack_per_player"]
        self.player_count  = start_state["player_count"]
        self.level_one_bb  = start_state["level_one_big_blind"]
        for p in start_state["players"]:
            if p["player_id"] != self.my_id:
                self.opponents[p["player_id"]] = OpponentModel(p["player_id"])

    def hand_ended(self, hand_history: dict):
        """Update opponent models from revealed information."""
        log = hand_history.get("hand_log", [])

        preflop_vpip: set  = set()
        preflop_raisers: set = set()

        for entry in log:
            pid    = entry["player_id"]
            if pid == self.my_id:
                continue
            if pid not in self.opponents:
                self.opponents[pid] = OpponentModel(pid)

            opp    = self.opponents[pid]
            action = entry["action"]
            stage  = entry.get("stage", "")

            if stage == "pre-flop":
                if action in ("call", "raise", "bet", "all-in"):
                    preflop_vpip.add(pid)
                if action in ("raise", "bet", "all-in"):
                    preflop_raisers.add(pid)
                    opp.agg_bets += 1
                elif action == "call":
                    opp.agg_calls += 1

            elif stage in ("flop", "turn", "river"):
                if action in ("bet", "raise", "all-in"):
                    opp.agg_bets += 1
                elif action == "call":
                    opp.agg_calls += 1

        for opp in self.opponents.values():
            opp.hands_seen += 1
            if opp.player_id in preflop_vpip:
                opp.vpip += 1
            if opp.player_id in preflop_raisers:
                opp.pfr += 1

        # Showdown data
        for result in hand_history.get("player_results", []):
            pid = result["player_id"]
            if pid == self.my_id or pid not in self.opponents:
                continue
            opp = self.opponents[pid]
            if result.get("hole_cards") and result["hand_status"] in ("active", "all-in"):
                opp.showdowns += 1
                if result.get("winnings", 0) > 0:
                    opp.showdown_wins += 1

    # ── Main decision ──────────────────────────────────────────────────────────
    def decide_action(self, game_state: dict) -> dict:
        stage          = game_state["current_stage"]
        hole           = game_state["hole_cards"]
        board          = game_state["community_cards"]
        bb             = game_state["big_blind"]
        ante           = game_state.get("ante", 0)
        small_blind    = game_state["small_blind"]
        my_status      = game_state["your_status"]
        my_stack       = my_status["stack"]
        my_pos         = my_status["position"]
        can_raise      = my_status["can_raise"]
        cost_to_match  = game_state["cost_to_match"]
        min_cost       = game_state["min_cost_to_increase"]
        bet_to_match   = game_state["bet_to_match"]
        players        = game_state["players"]

        n_players  = len(players)
        n_active   = sum(1 for p in players if p["hand_status"] == "active")
        total_pot  = sum(pot["amount"] for pot in game_state["pots"])

        # M-ratio: how many orbits of blinds our stack can survive
        orbit_cost = small_blind + bb + ante * n_players
        m_ratio    = my_stack / max(orbit_cost, 1)

        # Position: Dealer=0, SB=1, BB=2, UTG=3, …
        # Preflop late = dealer, SB, BB (they act last vs. limpers/raisers)
        # Postflop late = dealer (pos 0) acts last
        if stage == "pre-flop":
            is_late  = my_pos == 0 or my_pos >= n_players - 2
            is_early = 3 <= my_pos <= max(3, n_players // 2)
        else:
            is_late  = (my_pos == 0)
            is_early = my_pos in (1, 2)

        # Count callers/raisers ahead of us this street for table dynamics
        hand_log = game_state["hand_log"]

        if stage == "pre-flop":
            return self._preflop(
                hole, bb, my_stack, my_pos, n_players, n_active,
                cost_to_match, min_cost, bet_to_match, can_raise,
                m_ratio, is_late, is_early, total_pot, hand_log
            )
        else:
            return self._postflop(
                hole, board, bb, my_stack, my_pos, n_players, n_active,
                cost_to_match, min_cost, bet_to_match, can_raise,
                m_ratio, is_late, is_early, stage, total_pot, hand_log
            )

    # ── Preflop strategy ───────────────────────────────────────────────────────
    def _preflop(
        self, hole, bb, my_stack, my_pos, n_players, n_active,
        cost, min_cost, bet_to_match, can_raise,
        m, is_late, is_early, pot, hand_log
    ) -> dict:

        strength = preflop_strength(hole)

        # Count preflop raises by opponents
        pf_actions = [e for e in hand_log
                      if e.get("stage") == "pre-flop"
                      and e["player_id"] != self.my_id]
        n_raisers = sum(1 for e in pf_actions
                        if e["action"] in ("raise", "bet", "all-in"))
        n_callers = sum(1 for e in pf_actions
                        if e["action"] == "call")

        facing_raise    = cost > bb * 1.5
        facing_3bet_plus = n_raisers >= 2

        # ── Push/fold territory (short stack) ─────────────────────────────────
        if m < 10:
            return self._push_fold(
                strength, cost, min_cost, can_raise, my_stack,
                bb, n_active, pot, facing_raise
            )

        # ── Premium hands: AA, KK (strength >= 16) ────────────────────────────
        if strength >= 16:
            if can_raise:
                # Always re-raise large; try to build the pot
                amount = self._compute_raise(bet_to_match, bb, 3.5, min_cost, my_stack)
                return {"action": "increase", "amount": amount}
            return {"action": "match"}

        # ── Strong hands: QQ, JJ, AKs, AKo (strength >= 12) ──────────────────
        if strength >= 12:
            if can_raise:
                amount = self._compute_raise(bet_to_match, bb, 3, min_cost, my_stack)
                return {"action": "increase", "amount": amount}
            return {"action": "match"}

        # ── Solid hands: TT, AQs, AQo, AJs, KQs, 99 (strength >= 9) ──────────
        if strength >= 9:
            if facing_3bet_plus:
                # Fold marginal hands vs multiple raises
                if strength < 10:
                    return {"action": "fold"}
                return {"action": "match"}
            if facing_raise:
                if is_early and strength < 10:
                    return {"action": "fold"}
                # Call or 3-bet with premium end of this range
                if strength >= 11 and can_raise:
                    amount = self._compute_raise(bet_to_match, bb, 3, min_cost, my_stack)
                    return {"action": "increase", "amount": amount}
                return {"action": "match"}
            # No raise yet: open-raise
            if can_raise:
                # Raise bigger from early (more players to act), smaller from late
                multiplier = 2.5 if is_late else 3.0 + n_callers * 0.5
                amount = self._compute_raise(bb, bb, multiplier, min_cost, my_stack)
                return {"action": "increase", "amount": amount}
            return {"action": "match"}

        # ── Playable hands: 88-22, suited connectors, KJo, QJo (strength >= 5) ─
        if strength >= 5:
            if facing_3bet_plus:
                return {"action": "fold"}

            if facing_raise:
                # Call speculative hands only with good implied odds & position
                call_fraction = cost / max(my_stack, 1)
                if is_late and call_fraction < 0.07 and not is_early:
                    return {"action": "match"}   # set-mining / suited connector implied
                return {"action": "fold"}

            # Steal / open from late position
            if is_late:
                # Check how many opponents are tight/foldable
                fold_equity = self._estimate_fold_equity()
                if can_raise and fold_equity > 0.5:
                    amount = self._compute_raise(bb, bb, 2.5, min_cost, my_stack)
                    return {"action": "increase", "amount": amount}

            # Limp or check BB with speculative hands
            if cost == 0:
                return {"action": "match"}
            if cost <= bb and my_pos == 2:   # BB option
                return {"action": "match"}
            return {"action": "fold"}

        # ── Trash hands ────────────────────────────────────────────────────────
        if cost == 0:
            return {"action": "match"}   # free ride from BB
        return {"action": "fold"}

    def _push_fold(
        self, strength, cost, min_cost, can_raise, my_stack,
        bb, n_active, pot, facing_raise
    ) -> dict:
        """
        Short-stack push/fold logic.
        Threshold widens as M drops — we cannot afford to wait.
        """
        # Adaptive push thresholds by M-ratio
        # These are calibrated to Nash push/fold approximations
        m = my_stack / max(bb * 1.5, 1)   # rough M using just BB+SB
        if m < 3:
            push_thresh = 4       # push almost everything (desperation)
        elif m < 5:
            push_thresh = 7       # push 77+, A2s+, ATo+, KJs+
        elif m < 7:
            push_thresh = 9       # push 88+, AJ+, KQs
        else:
            push_thresh = 11      # push JJ+, AK

        if strength >= push_thresh:
            if can_raise:
                return {"action": "increase", "amount": my_stack}
            return {"action": "match"}    # can't raise, just call

        # Facing a raise, consider calling off if price is right
        if facing_raise and strength >= push_thresh - 3:
            pot_odds = cost / max(pot + cost, 1)
            if pot_odds < 0.35:
                return {"action": "match"}

        if cost == 0:
            return {"action": "match"}
        return {"action": "fold"}

    # ── Postflop strategy ──────────────────────────────────────────────────────
    def _postflop(
        self, hole, board, bb, my_stack, my_pos, n_players, n_active,
        cost, min_cost, bet_to_match, can_raise,
        m, is_late, is_early, stage, pot, hand_log
    ) -> dict:

        score  = best_hand_rank(hole, board)
        cat    = score[0] if score else -1    # 0=high card … 8=str-flush
        draws  = detect_draws(hole, board)
        wet    = board_wetness(board)

        top_pair  = self._is_top_pair(hole, board, score)
        overpair  = self._is_overpair(hole, board, score)
        good_kicker = self._has_good_kicker(hole, board, score)

        # Pot odds as a fraction of call vs pot
        pot_odds = cost / max(pot + cost, 1) if cost > 0 else 0

        # Whether we were the preflop aggressor (c-bet situation)
        pf_raiser = self._was_preflop_raiser(hand_log)

        # ── Monster hands: straight+, full house, quads, str-flush ────────────
        if cat >= 6:
            return self._value_bet(pot, cost, min_cost, bet_to_match, my_stack, can_raise, tier=3)

        # Flush or straight (made)
        if cat in (4, 5):
            return self._value_bet(pot, cost, min_cost, bet_to_match, my_stack, can_raise, tier=3)

        # Trips
        if cat == 3:
            return self._value_bet(pot, cost, min_cost, bet_to_match, my_stack, can_raise, tier=3)

        # Two pair
        if cat == 2:
            # On wet boards be a bit more cautious facing large bets
            if wet >= 4 and cost > pot * 0.7:
                return {"action": "match"}  # call, don't bloat further
            return self._value_bet(pot, cost, min_cost, bet_to_match, my_stack, can_raise, tier=2)

        # One pair
        if cat == 1:
            pair_rank = score[1]
            if overpair:
                # Overpair: strong but wet boards are dangerous
                if wet >= 4 and cost > pot * 0.8:
                    return {"action": "match"}
                return self._value_bet(pot, cost, min_cost, bet_to_match, my_stack, can_raise, tier=2)

            if top_pair and good_kicker:
                # TPTK: standard bet/call
                if wet >= 3 and cost > pot * 0.6 and not is_late:
                    return {"action": "match"}
                return self._value_bet(pot, cost, min_cost, bet_to_match, my_stack, can_raise, tier=1)

            if top_pair:
                # Top pair bad kicker: thinner value, more cautious
                if cost > pot * 0.5:
                    # Fold to large bets without strong draw backup
                    if not draws.get("fd") and not draws.get("oesd"):
                        if stage in ("turn", "river"):
                            return {"action": "fold"}
                if cost == 0:
                    if can_raise:
                        amount = max(min_cost, int(pot * 0.5))
                        return {"action": "increase", "amount": min(my_stack, amount)}
                    return {"action": "match"}
                return {"action": "match"} if pot_odds < 0.35 else {"action": "fold"}

            # Weak pair (not top, not pocket pair)
            if draws.get("fd") or draws.get("oesd"):
                # Pair + draw: call with reasonable odds
                if pot_odds < 0.4:
                    return {"action": "match"}
            if cost == 0:
                return {"action": "match"}   # check weak pair
            if pot_odds < 0.22:
                return {"action": "match"}   # cheap call
            return {"action": "fold"}

        # ── High card: bluffing, draws, fold equity ────────────────────────────
        if cat == 0 or cat == -1:
            fd   = draws.get("fd",   False)
            oesd = draws.get("oesd", False)
            gs   = draws.get("gs",   False)

            # Combo draw (fd + oesd): very strong semi-bluff
            if fd and oesd:
                equity = 0.54 if stage == "flop" else 0.27
                if pot_odds < equity:
                    return {"action": "match"}
                if can_raise and is_late:
                    amount = max(min_cost, int(pot * 0.65))
                    return {"action": "increase", "amount": min(my_stack, amount)}
                return {"action": "match"}

            if fd:
                equity = 0.36 if stage == "flop" else 0.18
                if pot_odds < equity:
                    return {"action": "match"}
                if can_raise and is_late and stage == "flop" and self._random.random() < 0.35:
                    # Semi-bluff with flush draw
                    amount = max(min_cost, int(pot * 0.6))
                    return {"action": "increase", "amount": min(my_stack, amount)}
                return {"action": "fold"} if pot_odds >= equity else {"action": "match"}

            if oesd:
                equity = 0.32 if stage == "flop" else 0.16
                if pot_odds < equity:
                    return {"action": "match"}
                return {"action": "fold"}

            if gs:
                equity = 0.16 if stage == "flop" else 0.08
                if pot_odds < equity * 0.85:
                    return {"action": "match"}
                return {"action": "fold"} if cost > 0 else {"action": "match"}

            # Pure bluff: only in position, heads-up, on certain boards
            if cost == 0:
                if (is_late and n_active == 1 and pf_raiser and stage == "flop"
                        and can_raise and self._random.random() < 0.40):
                    # c-bet as preflop raiser into one opponent
                    amount = max(min_cost, int(pot * 0.50))
                    return {"action": "increase", "amount": min(my_stack, amount)}
                # Delayed bluff / probe bet on turn
                if is_late and n_active == 1 and stage == "turn" and can_raise and self._random.random() < 0.25:
                    amount = max(min_cost, int(pot * 0.55))
                    return {"action": "increase", "amount": min(my_stack, amount)}
                return {"action": "match"}

            return {"action": "fold"}

        return {"action": "fold"}   # safety net

    # ── Helper methods ─────────────────────────────────────────────────────────
    def _compute_raise(
        self, reference: float, bb: float, multiplier: float,
        min_cost: int, my_stack: int
    ) -> int:
        """Compute raise amount as multiplier × reference, floored by min_cost."""
        amount = max(int(reference * multiplier), int(min_cost), int(bb * 2))
        return min(amount, my_stack)

    def _value_bet(
        self, pot, cost, min_cost, bet_to_match, my_stack, can_raise, tier: int
    ) -> dict:
        """
        Bet / raise for value.
        tier 1 = thin value (0.5 pot), 2 = solid (0.65 pot), 3 = premium (0.8 pot).
        """
        ratios = {1: 0.50, 2: 0.65, 3: 0.80}
        ratio  = ratios.get(tier, 0.60)

        if cost > 0:
            # Facing a bet: raise with solid/premium value, call with thin
            if can_raise and tier >= 2:
                raise_to = max(min_cost, int(bet_to_match * 2.5))
                return {"action": "increase", "amount": min(my_stack, raise_to)}
            return {"action": "match"}
        else:
            # No prior bet: we lead out
            if can_raise or True:   # we can always bet from 0-cost position
                bet_amount = max(min_cost, int(pot * ratio))
                if bet_amount >= my_stack:
                    return {"action": "increase", "amount": my_stack}   # jam
                if bet_amount > 0 and can_raise:
                    return {"action": "increase", "amount": bet_amount}
            return {"action": "match"}   # check if can't raise

    def _is_top_pair(self, hole, board, score) -> bool:
        if not score or score[0] != 1 or not board:
            return False
        top_board = max(_rank(c) for c in board)
        pair_rank  = score[1]
        hole_ranks = [_rank(c) for c in hole]
        return pair_rank == top_board and pair_rank in hole_ranks

    def _is_overpair(self, hole, board, score) -> bool:
        if not score or score[0] != 1 or not board:
            return False
        hr = [_rank(c) for c in hole]
        if hr[0] != hr[1]:
            return False
        return hr[0] > max(_rank(c) for c in board)

    def _has_good_kicker(self, hole, board, score) -> bool:
        """
        Consider kicker 'good' if our non-pair card is T or higher.
        """
        if not score or score[0] != 1:
            return False
        pair_rank  = score[1]
        hole_ranks = [_rank(c) for c in hole]
        kicker = [r for r in hole_ranks if r != pair_rank]
        return bool(kicker) and kicker[0] >= 8   # T = index 8

    def _was_preflop_raiser(self, hand_log: list) -> bool:
        """True if we were the last aggressor preflop."""
        last_agg = None
        for entry in hand_log:
            if entry.get("stage") == "pre-flop" and entry["action"] in ("bet", "raise", "all-in"):
                last_agg = entry["player_id"]
        return last_agg == self.my_id

    def _estimate_fold_equity(self) -> float:
        """
        Estimate probability that all opponents fold to a steal.
        Based on VPIP rates: tight players fold more to steals.
        """
        if not self.opponents:
            return 0.55    # default: moderate fold equity
        total_fold_prob = 1.0
        for opp in self.opponents.values():
            if opp.hands_seen < 3:
                # Unknown — assume moderate tightness
                fold_prob = 0.70
            else:
                # Tight/aggressive = folds to steals, loose/passive = calls
                vpip = opp.vpip_rate
                fold_prob = max(0.20, 1.0 - vpip - opp.pfr_rate * 0.5)
            total_fold_prob *= fold_prob
        return total_fold_prob