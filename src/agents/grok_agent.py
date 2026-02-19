from .base_agent import BasePokerAgent
import collections
import math

class GrokAgent(BasePokerAgent):
    def __init__(self, seed: int = None, name: str = "Grok Agent"):
        super().__init__(seed, name)
        self.opponent_models = {}
        self.total_hands = 0
        self.rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}

    def game_start(self, start_state):
        # Initialize opponent models with default stats
        self.player_count = start_state["player_count"]
        self.my_player_id = start_state["your_status"]["player_id"]
        self.opponent_models = {
            p["player_id"]: {
                "vpip_count": 0,
                "pfr_count": 0,
                "bet_raise_count": 0,
                "call_count": 0,
                "hands": 0
            } for p in start_state["players"] if p["player_id"] != self.my_player_id
        }

    def hand_ended(self, hand_history):
        # Update total hands and opponent stats based on the hand log
        self.total_hands += 1
        for pid in list(self.opponent_models.keys()):
            if any(pr["player_id"] == pid and pr["stack"] > 0 for pr in hand_history["player_results"]):
                self.opponent_models[pid]["hands"] += 1

        # Parse preflop actions for VPIP and PFR
        preflop_actions = [a for a in hand_history["hand_log"] if a["stage"] == "pre-flop"]
        for action in preflop_actions:
            pid = action["player_id"]
            if pid == self.my_player_id or pid not in self.opponent_models:
                continue
            if action["action"] in ["small-blind", "big-blind", "ante"]:
                continue
            if action["action"] in ["call", "bet", "raise", "all-in"]:
                self.opponent_models[pid]["vpip_count"] += 1
            if action["action"] in ["bet", "raise", "all-in"]:
                self.opponent_models[pid]["pfr_count"] += 1

        # Parse postflop actions for aggression factor
        postflop_actions = [a for a in hand_history["hand_log"] if a["stage"] != "pre-flop" and a["action"] not in ["ante"]]
        for action in postflop_actions:
            pid = action["player_id"]
            if pid == self.my_player_id or pid not in self.opponent_models:
                continue
            if action["action"] in ["bet", "raise", "all-in"]:
                self.opponent_models[pid]["bet_raise_count"] += 1
            if action["action"] == "call":
                self.opponent_models[pid]["call_count"] += 1

        # Clean up models for eliminated players
        self.opponent_models = {pid: model for pid, model in self.opponent_models.items() if any(pr["player_id"] == pid and pr["stack"] > 0 for pr in hand_history["player_results"])}

    def decide_action(self, game_state):
        # Core decision logic
        hole = game_state["hole_cards"]
        community = game_state["community_cards"]
        stage = game_state["current_stage"]
        my_status = game_state["your_status"]
        my_stack = my_status["stack"]
        my_position = my_status["position"]
        big_blind = game_state["big_blind"]
        effective_bb = my_stack / big_blind if big_blind > 0 else float('inf')
        pots = game_state["pots"]
        pot = sum(p["amount"] for p in pots)
        cost_to_match = game_state["cost_to_match"]
        min_cost_to_increase = game_state["min_cost_to_increase"]
        bet_to_match = game_state["bet_to_match"]
        pot_odds = cost_to_match / (pot + cost_to_match) if cost_to_match > 0 else 0
        players = game_state["players"]
        active_players = [p for p in players if p["hand_status"] == "active"]
        num_active = len(active_players)
        current_log = [a for a in game_state["hand_log"] if a["stage"] == stage]

        # Get opponent models (defaults for unknown)
        default_model = {"vpip": 0.25, "pfr": 0.15, "af": 2.0}

        # Short stack adjustment: push/fold mode if effective BB < 10
        if effective_bb < 10:
            return self.short_stack_logic(game_state, hole, pot, cost_to_match, min_cost_to_increase, my_stack, current_log)

        if stage == "pre-flop":
            return self.preflop_logic(game_state, hole, my_position, num_active, big_blind, bet_to_match, cost_to_match, min_cost_to_increase, my_stack, current_log, pot, default_model)

        else:
            return self.postflop_logic(game_state, hole, community, stage, my_position, pot, cost_to_match, min_cost_to_increase, my_stack, current_log, pot_odds, default_model)

    def short_stack_logic(self, game_state, hole, pot, cost_to_match, min_cost_to_increase, my_stack, current_log):
        # Push/fold for short stacks: push with top 40% hands if unopened or facing small bet, call all-in if pot odds justify
        hand_strength = self.get_preflop_hand_strength(hole)
        is_facing_raise = any(a["action"] in ["raise", "bet", "all-in"] for a in current_log)
        if cost_to_match == 0:
            # Push if good hand
            if hand_strength > 0.4:
                return {"action": "increase", "amount": my_stack}
            else:
                return {"action": "match"}
        else:
            # Facing bet: call if good odds or good hand
            pot_odds = cost_to_match / (pot + cost_to_match)
            if hand_strength > pot_odds + 0.1:  # Adjust for implied odds in tournament survival
                return {"action": "match"}
            elif hand_strength > 0.6 and not is_facing_raise:
                # Push over limp
                return {"action": "increase", "amount": my_stack}
            else:
                return {"action": "fold"}

    def preflop_logic(self, game_state, hole, my_position, num_active, big_blind, bet_to_match, cost_to_match, min_cost_to_increase, my_stack, current_log, pot, default_model):
        # Preflop strategy: open raise, isolate limps, 3bet, call, fold
        hand_strength = self.get_preflop_hand_strength(hole)
        is_facing_raise = bet_to_match > big_blind
        num_limpers = self.get_num_limpers(game_state)
        is_unopened = not is_facing_raise and num_limpers == 0

        position_cat = self.get_position_category(my_position, num_active)

        # Get last raiser if any
        raisers = [a["player_id"] for a in current_log if a["action"] in ["raise", "bet", "all-in"]]
        last_raiser = raisers[-1] if raisers else None
        raiser_model = self.get_opponent_model(last_raiser) if last_raiser else default_model

        # Adjust thresholds based on opponent (exploit loose/tight)
        vpip_adjust = (raiser_model["vpip"] - 0.25) * 0.2  # Looser opponent: tighter call, wider 3bet
        pfr_adjust = (raiser_model["pfr"] - 0.15) * 0.2

        if is_unopened:
            open_threshold = self.get_open_threshold(position_cat) - vpip_adjust  # Steal more vs tight
            if hand_strength > open_threshold:
                size = self.get_open_size(game_state, num_active, big_blind)
                amount = max(math.ceil(size), min_cost_to_increase)
                amount = min(amount, my_stack)
                return {"action": "increase", "amount": amount}
            else:
                if cost_to_match == 0:  # BB check
                    return {"action": "match"}
                else:
                    return {"action": "fold"}
        elif not is_facing_raise:
            # Facing limps: isolate with wider range
            iso_threshold = self.get_iso_threshold(position_cat, num_limpers) - vpip_adjust
            call_threshold = iso_threshold - 0.1
            if hand_strength > iso_threshold:
                size = self.get_iso_size(game_state, num_limpers, big_blind)
                amount = max(math.ceil(size), min_cost_to_increase)
                amount = min(amount, my_stack)
                return {"action": "increase", "amount": amount}
            elif hand_strength > call_threshold and position_cat in ["button", "small_blind"]:
                return {"action": "match"}
            else:
                if cost_to_match == 0:
                    return {"action": "match"}
                else:
                    return {"action": "fold"}
        else:
            # Facing raise: 3bet or call
            threebet_threshold = self.get_threebet_threshold(position_cat, raiser_model) + pfr_adjust  # Tighter vs aggressive raiser
            call_threshold = self.get_call_threshold(position_cat, raiser_model, game_state) - vpip_adjust  # Wider call vs loose
            if hand_strength > threebet_threshold and game_state["your_status"]["can_raise"]:
                size = self.get_threebet_size(game_state, bet_to_match, big_blind)
                amount = max(math.ceil(size), min_cost_to_increase)
                amount = min(amount, my_stack)
                return {"action": "increase", "amount": amount}
            elif hand_strength > call_threshold:
                return {"action": "match"}
            else:
                return {"action": "fold"}

    def postflop_logic(self, game_state, hole, community, stage, my_position, pot, cost_to_match, min_cost_to_increase, my_stack, current_log, pot_odds, default_model):
        # Postflop strategy: value bet/raise, semi-bluff, check/call/fold based on hand strength and draws
        hand_type = self.evaluate_hand(hole, community)
        category = hand_type[0]
        pair_type = self.get_pair_strength(hole, community)
        flush_draw = self.has_flush_draw(hole, community)
        straight_draw = self.has_straight_draw(hole, community)

        # Classify hand strength
        is_strong = (
                category >= 4 or
                category == 3 or
                (category == 2 and len(hand_type) > 1 and isinstance(hand_type[1], tuple) and hand_type[1][0] >= 10) or
                (pair_type in ["overpair", "top_pair"] and len(hand_type) > 2 and isinstance(hand_type[2], int) and
                 hand_type[2] >= 11)
        )
        is_medium = category in [1, 2] or pair_type in ["top_pair", "middle_pair"] or flush_draw == True or straight_draw == "oed"
        is_weak = not is_strong and not is_medium
        has_draw = flush_draw == True or straight_draw in ["oed", "gutshot"]

        # Adjust for board texture (aggressive on dry, cautious on wet)
        wet_board = len(set(c[1] for c in community)) <= 2 or self.check_straight(communityRanks := sorted(set(self.rank_map[c[0]] for c in community)))

        # Get last bettor
        bettors = [a["player_id"] for a in current_log if a["action"] in ["bet", "raise", "all-in"]]
        last_bettor = bettors[-1] if bettors else None
        bettor_model = self.get_opponent_model(last_bettor) if last_bettor else default_model

        # Position adjustment: more aggression in position (low position number = late to act)
        in_position = my_position <= self.player_count // 2  # Lower position = later act

        if cost_to_match == 0:
            # Unbetted: bet for value or bluff
            bluff_prob = 0.3 if stage == "flop" else 0.2 if stage == "turn" else 0.1
            if bettor_model["af"] < 1.5:  # Bluff more vs passive
                bluff_prob += 0.1
            if is_strong or (has_draw and self._random.random() < bluff_prob and in_position and not wet_board):
                bet_size = self.get_bet_size(stage, pot, wet_board)
                amount = max(math.ceil(bet_size), min_cost_to_increase)
                amount = min(amount, my_stack)
                return {"action": "increase", "amount": amount}
            else:
                return {"action": "match"}
        else:
            # Facing bet: raise for value, call with medium/draw if odds good, fold weak
            if is_strong and (bettor_model["vpip"] > 0.3 or not wet_board):  # Value raise vs loose
                raise_size = self.get_raise_size(stage, bet_to_match, pot, wet_board)
                amount = max(math.ceil(raise_size), min_cost_to_increase)
                amount = min(amount, my_stack)
                return {"action": "increase", "amount": amount}
            elif is_medium and pot_odds < 0.25:  # Call if good odds (tournament survival: tighter on river)
                if stage == "river":
                    if pot_odds < 0.2:
                        return {"action": "match"}
                else:
                    return {"action": "match"}
            elif has_draw and pot_odds < 0.2 and stage != "river" and bettor_model["af"] < 2:  # Call draws vs passive
                return {"action": "match"}
            else:
                return {"action": "fold"}

    # Helper functions

    def get_opponent_model(self, pid):
        if pid not in self.opponent_models:
            return {"vpip": 0.25, "pfr": 0.15, "af": 2.0}
        model = self.opponent_models[pid]
        hands = model["hands"]
        vpip = model["vpip_count"] / hands if hands > 0 else 0.25
        pfr = model["pfr_count"] / hands if hands > 0 else 0.15
        af = model["bet_raise_count"] / model["call_count"] if model["call_count"] > 0 else 2.0
        return {"vpip": vpip, "pfr": pfr, "af": af}

    def get_preflop_hand_strength(self, hole):
        # Heuristic strength score 0-1 for preflop hands (higher = better)
        r1, s1 = hole[0][0], hole[0][1]
        r2, s2 = hole[1][0], hole[1][1]
        ranks = sorted([self.rank_map[r1], self.rank_map[r2]], reverse=True)
        suited = s1 == s2
        if ranks[0] == ranks[1]:  # Pairs
            return 0.6 + (ranks[0] - 2) / 12 * 0.4  # 22: 0.6, AA: 1.0
        base = (ranks[0] + ranks[1] - 4) / 24 * 0.4  # Scale sum
        if suited:
            base += 0.2
        if abs(ranks[0] - ranks[1]) <= 2:
            base += 0.1
        if min(ranks) >= 10:
            base += 0.1
        if ranks[0] == 14:
            base += 0.1
        return min(base, 1.0)

    def get_position_category(self, my_position, num_active):
        # Categorize position for range adjustment
        if num_active <= 2:
            return "heads_up"
        co = (num_active - 1) % num_active
        hj = (num_active - 2) % num_active
        if my_position == 0:
            return "button"
        if my_position == co:
            return "cutoff"
        if my_position == hj:
            return "hijack"
        if my_position == 1:
            return "small_blind"
        if my_position == 2:
            return "big_blind"
        return "early" if my_position >= 3 and my_position < num_active // 2 + 3 else "middle"

    def get_open_threshold(self, position_cat):
        # Threshold for opening unraised pots (lower = wider range)
        thresholds = {
            "early": 0.65,
            "middle": 0.55,
            "hijack": 0.45,
            "cutoff": 0.35,
            "button": 0.25,
            "small_blind": 0.3,
            "big_blind": 0.0,  # Check
            "heads_up": 0.2
        }
        return thresholds.get(position_cat, 0.65)

    def get_open_size(self, game_state, num_active, big_blind):
        # Open size: smaller in late position, add for antes
        base = 2.5 if num_active > 4 else 2.2
        if game_state["ante"] > 0:
            base += 0.5
        return base * big_blind

    def get_num_limpers(self, game_state):
        # Count limpers before me
        bet_to_match = game_state["bet_to_match"]
        my_pos = game_state["your_status"]["position"]
        limpers = 0
        for p in game_state["players"]:
            if p["hand_status"] == "active" and p["position"] > 2 and p["position"] < my_pos and p["current_bet_this_stage"] == bet_to_match:
                limpers += 1
        return limpers

    def get_iso_threshold(self, position_cat, num_limpers):
        # Threshold for isolating limps (wider with more limpers)
        base = self.get_open_threshold(position_cat) + 0.05 * num_limpers
        return max(0.3, base - 0.1)  # Wider in position

    def get_iso_size(self, game_state, num_limpers, big_blind):
        # Isolate size: larger with more limpers
        base = 3 + num_limpers
        if game_state["ante"] > 0:
            base += 1
        return base * big_blind

    def get_threebet_threshold(self, position_cat, raiser_model):
        # Threshold for 3betting (tighter OOP, wider vs loose opens)
        base = 0.7 if position_cat in ["early", "middle", "big_blind"] else 0.6
        adjust = (0.25 - raiser_model["pfr"]) * 0.2  # 3bet wider vs low PFR (weak opens)
        return base + adjust

    def get_call_threshold(self, position_cat, raiser_model, game_state):
        # Threshold for calling raises (wider in position, vs loose raiser)
        base = 0.5 if position_cat in ["button", "cutoff", "big_blind"] else 0.6
        adjust = (raiser_model["vpip"] - 0.25) * 0.2  # Wider call vs loose
        pot_odds_adjust = game_state["cost_to_match"] / (sum(p["amount"] for p in game_state["pots"]) + game_state["cost_to_match"]) * 0.1
        return base - adjust - pot_odds_adjust

    def get_threebet_size(self, game_state, bet_to_match, big_blind):
        # 3bet size: 3x facing size, larger OOP or with antes
        facing_size = bet_to_match / big_blind
        base = 3 * facing_size
        if game_state["your_status"]["position"] > 2:  # OOP larger
            base += 1
        if game_state["ante"] > 0:
            base += 0.5
        return base * big_blind

    def evaluate_hand(self, hole, board):
        # Simple hand evaluator returning (category, tiebreakers)
        # Categories: 8=straight flush, 7=quads, 6=full, 5=flush, 4=straight, 3=three, 2=two pair, 1=pair, 0=high
        cards = hole + board
        ranks = [self.rank_map[c[0]] for c in cards]
        suits = [c[1] for c in cards]
        sorted_ranks = sorted(ranks, reverse=True)
        count = collections.Counter(ranks)
        suit_groups = collections.defaultdict(list)
        for i, r in enumerate(ranks):
            suit_groups[suits[i]].append(r)
        for sg in suit_groups:
            suit_groups[sg].sort(reverse=True)

        # Flush suit
        flush_suit = max(suit_groups, key=lambda s: len(suit_groups[s])) if max(len(suit_groups[s]) for s in suit_groups) >= 5 else None

        # Straight flush
        if flush_suit:
            fr = sorted(suit_groups[flush_suit], reverse=True)
            sf, sf_high = self.check_straight(fr)
            if sf:
                return (8, sf_high)

        # Quads
        quads = [r for r in count if count[r] == 4]
        if quads:
            qr = max(quads)
            kicker = max(r for r in sorted_ranks if r != qr)
            return (7, qr, kicker)

        # Full house
        threes = [r for r in count if count[r] == 3]
        pairs = [r for r in count if count[r] == 2]
        if threes and (pairs or len(threes) >= 2):
            tr = max(threes)
            pr = max(pairs) if pairs else sorted(threes)[-2]
            return (6, tr, pr)

        # Flush
        if flush_suit:
            fr = tuple(suit_groups[flush_suit][:5])
            return (5, fr)

        # Straight
        ur = sorted(set(ranks), reverse=True)
        st, sh = self.check_straight(ur)
        if st:
            return (4, sh)

        # Three of a kind
        if threes:
            tr = max(threes)
            kickers = sorted([r for r in set(ranks) if r != tr], reverse=True)[:2]
            return (3, tr, tuple(kickers))

        # Two pair
        if len(pairs) >= 2:
            prs = sorted(pairs, reverse=True)[:2]
            kicker = max(r for r in set(ranks) if r not in prs)
            return (2, tuple(prs), kicker)

        # Pair
        if pairs:
            pr = max(pairs)
            kickers = sorted([r for r in set(ranks) if r != pr], reverse=True)[:3]
            return (1, pr, tuple(kickers))

        # High card
        return (0, tuple(sorted_ranks[:5]))

    def check_straight(self, sorted_ranks):
        if len(sorted_ranks) < 5:
            return False, 0
        # Wheel
        if 14 in sorted_ranks and all(x in sorted_ranks for x in [2, 3, 4, 5]):
            return True, 5
        for i in range(len(sorted_ranks) - 4):
            if sorted_ranks[i] - sorted_ranks[i + 4] == 4:
                return True, sorted_ranks[i]
        return False, 0

    def get_pair_strength(self, hole, board):
        # Classify pair type relative to board
        board_ranks = sorted([self.rank_map[c[0]] for c in board], reverse=True)
        hole_ranks = [self.rank_map[c[0]] for c in hole]
        paired_rank = None
        if hole_ranks[0] == hole_ranks[1]:
            paired_rank = hole_ranks[0]
        else:
            for hr in hole_ranks:
                if hr in board_ranks:
                    paired_rank = hr
                    break
        if not paired_rank:
            return None
        top = board_ranks[0] if board_ranks else 0
        if paired_rank > top:
            return "overpair"
        if paired_rank == top:
            return "top_pair"
        if len(board_ranks) > 1 and paired_rank == board_ranks[1]:
            return "middle_pair"
        return "bottom_pair"

    def has_flush_draw(self, hole, board):
        suits = [c[1] for c in hole + board]
        count = collections.Counter(suits)
        max_c = max(count.values())
        if max_c >= 5:
            return "flush_made"
        if max_c == 4:
            return True
        return False

    def has_straight_draw(self, hole, board):
        ranks = sorted(set([self.rank_map[c[0]] for c in hole + board]))
        if len(ranks) < 4:
            return None
        # Open-ended
        for i in range(len(ranks) - 3):
            if ranks[i + 3] - ranks[i] == 3:
                return "oed"
        # Gutshot
        for i in range(len(ranks) - 3):
            if ranks[i + 3] - ranks[i] == 4:
                return "gutshot"
        # Wheel draws
        low_set = {2, 3, 4, 5, 14}
        if len(low_set.intersection(ranks)) == 4:
            return "gutshot" if 14 in ranks else "oed"
        return None

    def get_bet_size(self, stage, pot, wet_board):
        # Bet sizing: smaller on wet boards, larger on river
        frac = 0.66 if stage == "flop" else 0.5 if stage == "turn" else 0.75
        if wet_board:
            frac -= 0.16
        return frac * pot

    def get_raise_size(self, stage, bet_to_match, pot, wet_board):
        # Raise sizing: 3x on dry, smaller on wet
        base = 2.5 * bet_to_match + pot
        if wet_board:
            base *= 0.8
        if stage == "river":
            base *= 1.2
        return base