from player import Player
from chip_stack import ChipStack
from treys import Card, Deck, Evaluator
from agents.input_agent import InputAgent
from copy import deepcopy

def card_list2str(card_list: list[int]):
    str_list = []
    for card in card_list:
        str_list.append(Card.int_to_str(card))
    return str_list

def get_player_result(player: Player, reveal: bool = False):
    if reveal:
        assert player.score > 0
    result = {
        'player_id': player.player_id,
        'hand_status': player.hand_status,
        'hole_cards': card_list2str(player.hole_cards) if reveal else None,
        'score': player.score if reveal else None,
        'total_bet_this_hand': player.total_bet_this_hand,
        'winnings': player.total_gain_this_hand,
        'stack': player.stack.amount,
        'rank': player.rank
    }
    return result

class InvalidStringError(Exception):
    """Raised when an invalid or illegal string is found."""
    pass


class Hand:
    def __init__(
            self,
            player_list: list[Player],
            hand_id: int,
            ante: int,
            small_blind: int,
            big_blind: int,
            big_blind_ante: int,
            deck: Deck
    ):
        assert 2 <= len(player_list) <= 10
        assert len(player_list) == len(set(player_list)) # No duplicated players
        self.player_list = player_list
        self.hand_id = hand_id
        self.ante = ante
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.big_blind_ante = big_blind_ante
        self.deck = deck
        self.current_stage = None
        self.community_cards = []
        self.pot_stacks = []
        self.evaluator = Evaluator()
        self.hand_log = []
        main_pot = {
            'stack': ChipStack(),
            'eligible_players': []
        }
        self.pot_stacks.append(main_pot)

    def get_positions(self):
        """Yields indexes of Dealer, Small Blind, Big Blind and Under the Gun."""
        n = len(self.player_list)

        if n == 2:
            yield 0     # Dealer
            yield 0     # Small Blind
            yield 1     # Big Blind
            yield 0     # Under the Gun
            return

        yield 0         # Dealer
        yield 1         # Small Blind
        yield 2         # Big Blind
        yield 3 % n     # Under the Gun

    def deal_hole_cards(self, index: int):
        """Deals cards, usually start with small blind."""
        self.deck.shuffle()

        for _ in range(len(self.player_list)):
            hole_cards = self.deck.draw(2)
            self.player_list[index].receive_hole_cards(hole_cards)
            index += 1
            if index == len(self.player_list):
                index = 0

    def deal_community_cards(self, amount: int):
        """Deals community cards."""
        if amount < 0:
            raise ValueError("Cannot deal negative amount of community cards")
        self.community_cards = self.community_cards + self.deck.draw(amount)

    def log(self, player: Player, stack_before: int, action: str, cost: int, stage: str):
        if action not in ['ante', 'small-blind', 'big-blind', 'big-blind-ante', 'bet', 'check', 'fold', 'call', 'raise', 'all-in']:
            raise InvalidStringError(f"Undefined action '{action}'")
        if stage not in ['ante', 'pre-flop', 'flop', 'turn', 'river']:
            raise InvalidStringError(f"Undefined stage '{stage}'")
        log_item = {
            'player_id': player.player_id,
            'stack_before': stack_before,
            'action': action,
            'cost': cost,
            'stage': stage
        }
        self.hand_log.append(log_item)

    def get_player_status(self, player: Player):
        player_status = {
            'position': self.player_list.index(player),
            'player_id': player.player_id,
            'stack': player.stack.amount,
            'hand_status': player.hand_status,
            'current_bet_this_stage': player.unresolved_chips,
            'total_bet_this_hand': player.total_bet_this_hand,
            'can_raise': player.can_raise
        }
        return player_status

    def get_game_state(self, player: Player, stack: ChipStack, bet_to_call: int, min_raise: int):
        current_stage = self.current_stage

        hole_cards = card_list2str(player.hole_cards)

        community_cards = card_list2str(self.community_cards)

        pots = []
        competing_players = self.get_competing_players()
        for pot in self.pot_stacks:
            amount = pot['stack'].amount
            if amount == 0:
                continue
            eligible_players = list(set(competing_players) & set(pot['eligible_players']))
            eligible_players = [p.player_id for p in eligible_players]
            pot_dict = {
                'amount': amount,
                'eligible_players': eligible_players
            }
            pots.append(pot_dict)

        players = []
        for p in self.player_list:
            players.append(self.get_player_status(p))

        logs = self.hand_log

        # current_stage_logs = [
        #     log for log in self.hand_log
        #     if log['stage'] == current_stage
        # ]
        # n = len(self.player_list)
        # recent_history = current_stage_logs[-n:]

        game_state = {
            # --- PRIVATE INFO (Only this player sees this) ---
            "hole_cards": hole_cards,  # Your 2 cards

            # --- PUBLIC SHARED INFO ---
            "hand_id": self.hand_id,
            "community_cards": community_cards,
            "current_stage": current_stage,  # "pre-flop", "flop", "turn", "river"
            "stage_pot": stack.amount,
            "pots": pots,

            # --- YOUR STATUS ---
            "your_status": self.get_player_status(player),

            # --- BETTING MATH ---
            "bet_to_match": bet_to_call,             # Bet you have to match if you want to check or call
            "min_increase": min_raise,                 # Minimum amount to increase by if you want to bet or raise
            "cost_to_match": bet_to_call - player.unresolved_chips,  # How much you have to pay if you want to check or call
            "min_cost_to_increase": bet_to_call - player.unresolved_chips + min_raise, # How much at least you have to pay if you want to bet or raise
            "small_blind": self.small_blind,                # Reference for sizing bets
            "big_blind": self.big_blind,                    # Reference for sizing bets
            "ante": max(self.ante, self.big_blind_ante),    # Reference for sizing bets

            # --- PLAYER STATUS ---
            # A list of everyone at the table (ordered by position)
            "players": players,

            # --- ACTION HISTORY (Crucial for detecting logic) ---
            # A list of sequential actions in the current hand
            "hand_log": logs
        }

        isolated_state = deepcopy(game_state)

        return isolated_state

    def get_player_results(self, revealing_players: list[Player]):
        player_results = []
        for player in self.player_list:
            reveal = True if player in revealing_players else False
            result = get_player_result(player, reveal)
            player_results.append(result)
        return player_results

    def get_hand_history(self, player: Player, competing_players, player_results):
        community_cards = card_list2str(self.community_cards)

        end_at = self.current_stage
        reveal = True if end_at == 'showdown' and player in competing_players else False

        hand_history = {
            'hand_id': self.hand_id,
            'ante': max(self.ante, self.big_blind_ante),
            'small_blind': self.small_blind,
            'big_blind': self.big_blind,
            'community_cards': community_cards,
            'end_at': end_at,
            'your_result': get_player_result(player, reveal),
            'player_results': player_results,
            'hand_log': self.hand_log
        }

        isolated_history = deepcopy(hand_history)

        return isolated_history

    def hand_ended(self):
        eliminated = [p for p in self.player_list if p.stack.amount == 0]
        eliminated.sort(key=lambda p: p.total_bet_this_hand, reverse=True)
        alive = [p for p in self.player_list if p.stack.amount != 0]
        previous_player = None
        alive_count = len(alive)
        hand_id = self.hand_id
        assert alive_count >= 1

        for i in range(len(eliminated)):
            player = eliminated[i]
            player.update_rank(alive_count + 1 + i, hand_id)
            if previous_player:
                assert player.total_bet_this_hand <= previous_player.total_bet_this_hand
                if player.total_bet_this_hand == previous_player.total_bet_this_hand:
                    player.update_rank(previous_player.rank, hand_id)
            previous_player = player

        if alive_count == 1:
            alive[0].update_rank(1, hand_id)

        competing_players = self.get_competing_players()
        revealing_players = competing_players if self.current_stage == 'showdown' else []
        player_results = self.get_player_results(revealing_players)
        for player in self.player_list:
            hand_history = self.get_hand_history(player, competing_players, player_results)
            player.agent.hand_ended(hand_history)

        # If player stack is assigned a rank, set their game status to 'finished'
        for player in self.player_list:
            player.check_alive()

    def add_to_pots_bba(self, stack: ChipStack):
        contributors = [player for player in self.player_list if player.unresolved_chips != 0]
        assert len(contributors) == 1
        _, _, bb, _ = self.get_positions()
        big_blind = self.player_list[bb]
        assert contributors[0] == big_blind

        pot = self.pot_stacks[-1]

        amount = big_blind.unresolved_chips
        pot['stack'].add(stack.pop(amount))
        pot['eligible_players'] = self.player_list.copy()
        big_blind.resolve(amount)

        if big_blind.hand_status == 'all-in':
            new_side_pot = {
                'stack': ChipStack(),
                'eligible_players': []
            }
            self.pot_stacks.append(new_side_pot)

    # Extremely messy codes here. Should exist a better implementation
    def add_to_pots(self, stack: ChipStack):
        """Resolves chips from a temporary stack."""
        contributors = [player for player in self.player_list if player.unresolved_chips != 0]
        all_iners = [player for player in contributors if player.hand_status == 'all-in']
        non_all_iners = [player for player in contributors if player not in all_iners]

        # Sorted by total committed chips this stage, from high to low
        all_iners.sort(key=lambda p: p.unresolved_chips, reverse=True)

        # When a player all-ins, move chips to the current pot and create a new pot that excludes this player
        while all_iners:
            least_committed = all_iners.pop()
            pot_increase = least_committed.unresolved_chips

            # DEBUG
            # print(least_committed.player_id)
            # print(pot_increase)

            pot = self.pot_stacks[-1]
            if pot_increase == 0:
                # Current pot will be empty
                assert self.pot_stacks[-1]['stack'].amount == 0
                pass
            else:
                # Current pot will not be empty, add chips to it


                for player in non_all_iners + all_iners + [least_committed]:
                    amount = min(pot_increase, player.unresolved_chips)
                    pot['stack'].add(stack.pop(amount))
                    if player not in pot['eligible_players']:
                        pot['eligible_players'].append(player)
                    player.resolve(amount)

                # Create a new side pot
                new_side_pot = {
                    'stack': ChipStack(),
                    'eligible_players': []
                }
                self.pot_stacks.append(new_side_pot)

        # For players who don't all-in just move their chips to the current pot
        for player in non_all_iners:
            pot = self.pot_stacks[-1]
            pot['stack'].add(stack.pop(player.unresolved_chips))
            if player not in pot['eligible_players']:
                pot['eligible_players'].append(player)
            player.resolve(player.unresolved_chips)

        assert stack.amount == 0

    def get_max_bet(self):
        return max(p.unresolved_chips for p in self.player_list)

    def betting_round(self, stack: ChipStack, current_player: int, bet_to_call: int, min_raise: int):
        retry_count = 0     # Times failed to find the next active player
        while retry_count < len(self.player_list) - 1:
            # Automatically end the betting round when there's less than 2 active players
            active_players = self.get_active_players()
            if len(active_players) == 1:
                if active_players[0].unresolved_chips == bet_to_call:
                    return
            elif len(active_players) == 0:
                return

            # Pick the next player in order
            player = self.player_list[current_player]
            actable = player.is_actable(bet_to_call)
            if actable:

                game_state = self.get_game_state(player, stack, bet_to_call, min_raise)
                action = player.agent.decide_action(game_state)
                stack_before = player.stack.amount
                bet_to_call_before = bet_to_call
                cost = 0

                if action['action'] == 'fold':
                    player.fold()
                    action_name = 'fold'

                elif action['action'] == 'match':
                    cost = player.bet(stack, bet_to_call - player.unresolved_chips)

                    if player.hand_status == 'all-in':
                        action_name = 'all-in'
                    elif bet_to_call_before == 0:
                        action_name = 'check'
                    else:
                        action_name = 'call'

                elif action['action'] == 'increase':
                    can_raise = player.can_raise
                    # Call first
                    cost = player.bet(stack, bet_to_call - player.unresolved_chips)

                    # When player cannot raise it's just a call
                    if player.hand_status == 'all-in':
                        action_name = 'all-in'
                    else:
                        action_name = 'call'

                    if can_raise:
                        # This is the amount player wants to increase by
                        amount = max(action['amount'] - cost, min_raise)
                        # Raise
                        actual_raise = player.bet(stack, amount)

                        # DEBUG
                        # print("A raise!")
                        # print(Card.print_pretty_cards(self.community_cards))
                        # print(Card.print_pretty_cards(player.hole_cards))

                        # When it's a full raise
                        if actual_raise >= min_raise:
                            min_raise = actual_raise
                            # Open raise for everyone else
                            for p in self.player_list:
                                if p is player:
                                    continue
                                p.set_raise()
                        # Update bet to call. It only goes up never goes down
                        bet_to_call = max(self.get_max_bet(), bet_to_call)

                        cost += actual_raise
                        if player.hand_status == 'all-in':
                            action_name = 'all-in'
                        elif bet_to_call_before == 0:
                            action_name = 'bet'
                        else:
                            action_name = 'raise'

                else:
                    raise InvalidStringError(f"Undefined action '{action['action']}'")

                # Log the action
                self.log(player, stack_before, action_name, cost, self.current_stage)

            # If player acted and did not fold, next retry starts with retry count set to 0
            if actable and not player.hand_status == 'folded':
                retry_count = 0
            else:
                retry_count += 1

            current_player += 1
            if current_player == len(self.player_list):
                current_player = 0

    def get_competing_players(self):
        """Returns all players who have NOT folded."""
        return [p for p in self.player_list if p.hand_status != 'folded']

    def get_active_players(self):
        """Returns all players who are active."""
        return [p for p in self.player_list if p.hand_status == 'active']

    def check_uncontested_win(self):
        """
        Checks if only one player remains.
        If yes, awards them the pot immediately.
        Returns True if the hand ended, False otherwise.
        """

        # DEBUG
        # current_stage = self.current_stage
        # print(f"Hand {self.hand_id} Stage {current_stage}")
        # log = [l for l in self.hand_log if l['stage'] == current_stage]
        # for item in log:
        #     print(item)

        competing_players = self.get_competing_players()
        assert len(competing_players) > 0

        if len(competing_players) == 1:
            winner = competing_players[0]
            while self.pot_stacks:
                pot = self.pot_stacks.pop()

                # DEBUG
                # print(f"Resolving {pot['stack']}")
                # for p in pot['eligible_players']:
                #     print(p.player_id)

                if pot['stack'].amount == 0:
                    continue

                # Refund
                if winner not in pot['eligible_players']:
                    assert len(pot['eligible_players']) == 1
                    pot['eligible_players'][0].gain(pot['stack'], pot['stack'].amount)
                    continue

                assert winner in pot['eligible_players']
                winner.gain(pot['stack'], pot['stack'].amount)

            return True

        return False

    def collect_antes(self):
        self.current_stage = 'ante'
        stack = ChipStack()

        if self.ante:
            for player in self.player_list:
                player.stage_start()
                stack_before = player.stack.amount

                cost = player.bet(stack, self.ante)

                if player.hand_status == 'all-in':
                    action_name = 'all-in'
                else:
                    action_name = 'ante'

                self.log(player, stack_before, action_name, cost, 'ante')

            self.add_to_pots(stack)

        elif self.big_blind_ante:
            _, _, bb, _ = self.get_positions()
            big_blind = self.player_list[bb]
            stack_before = big_blind.stack.amount

            cost = big_blind.bet(stack, self.big_blind_ante)

            if big_blind.hand_status == 'all-in':
                action_name = 'all-in'
            else:
                action_name = 'big-blind-ante'

            self.log(big_blind, stack_before, action_name, cost, 'ante')

            self.add_to_pots_bba(stack)

    def run_preflop(self):
        self.current_stage = 'pre-flop'
        stack = ChipStack()
        _, sb, bb, utg = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        small_blind = self.player_list[sb]
        big_blind = self.player_list[bb]
        stack_before_sb = small_blind.stack.amount
        stack_before_bb = big_blind.stack.amount

        # Collect blinds
        cost_sb = small_blind.bet(stack, self.small_blind)
        cost_bb = big_blind.bet(stack, self.big_blind)

        # Blinds still get a chance to act voluntarily
        self.player_list[sb].set_raise()
        self.player_list[bb].set_raise()

        if small_blind.hand_status == 'all-in':
            action_name_sb = 'all-in'
        else:
            action_name_sb = 'small-blind'

        if big_blind.hand_status == 'all-in':
            action_name_bb = 'all-in'
        else:
            action_name_bb = 'big-blind'

        self.log(small_blind, stack_before_sb, action_name_sb, cost_sb, 'pre-flop')
        self.log(big_blind, stack_before_bb, action_name_bb, cost_bb, 'pre-flop')

        # Deal cards, starting with small blind
        self.deal_hole_cards(index=sb)

        # Start Pre-flop betting round
        current_player = utg
        bet_to_call = self.big_blind    # During Pre-flop, min bet to call = big blind, no matter how much the BB paid
        min_raise = self.big_blind
        self.betting_round(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_flop(self):
        self.current_stage = 'flop'
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 3 community cards
        self.deal_community_cards(3)

        # Start Flop betting round
        current_player = sb # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_round(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_turn(self):
        self.current_stage = 'turn'
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 1 community card
        self.deal_community_cards(1)

        # Start Turn betting round
        current_player = sb  # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_round(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_river(self):
        self.current_stage = 'river'
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 1 community card
        self.deal_community_cards(1)

        # Start River betting round
        current_player = sb  # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_round(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def showdown(self):
        if len(self.community_cards) != 5:
            raise ValueError("5 community cards are needed for showdown")
        self.current_stage = 'showdown'

        competing_players = self.get_competing_players()
        assert len(competing_players) > 1

        while self.pot_stacks:
            pot = self.pot_stacks.pop()
            if pot['stack'].amount == 0:
                continue

            # DEBUG
            # print(f"{pot['stack']}")
            # print(f"{pot['eligible_players']}")

            eligible_players = list(set(competing_players) & set(pot['eligible_players']))
            player_scores = []
            for player in eligible_players:
                if len(player.hole_cards) != 2:
                    raise ValueError("Each player should have 2 hole cards at showdown")
                score = self.evaluator.evaluate(player.hole_cards, self.community_cards)
                player.update_score(score)
                player_scores.append((player, score))
            player_scores.sort(key=lambda x: x[1])
            best_score = player_scores[0][1]
            winners = [p for p, score in player_scores if score == best_score]
            pot_amount = pot['stack'].amount
            num_winners = len(winners)
            split_amount = pot_amount // num_winners
            odd_chips = pot_amount % num_winners

            for winner in winners:
                winner.gain(pot['stack'], split_amount)

            if odd_chips > 0:
                _, index, _, _ = self.get_positions()
                while odd_chips:
                    player = self.player_list[index]
                    if player in winners:
                        player.gain(pot['stack'], 1)
                        odd_chips -= 1
                    index += 1
                    if index == len(self.player_list):
                        index = 0

            assert pot['stack'].amount == 0

    def run_hand(self):
        self.collect_antes()
        stages = [
            self.run_preflop,
            self.run_flop,
            self.run_turn,
            self.run_river
        ]

        # Iterate through each stage
        for stage_method in stages:
            stage_method()  # Execute the deal and betting for this stage

            # Did everyone fold?
            if self.check_uncontested_win():
                self.hand_ended()
                return  # Exit run_hand immediately

        # If we survive all stages without a fold-win, it's a showdown
        self.showdown()
        self.hand_ended()


if __name__ == '__main__':
    player_names = {
        0: "Alice",
        1: "Bob",
        2: "Clementine",
        3: "Dave"
    }
    alice = Player(0, InputAgent(player_names=player_names), "Alice")
    bob = Player(1, InputAgent(player_names=player_names), "Bob")
    clementine = Player(2, InputAgent(player_names=player_names), "Clementine")
    dave = Player(3, InputAgent(player_names=player_names), "Dave")

    alice.stack.add(20)
    bob.stack.add(9)
    clementine.stack.add(20)
    dave.stack.add(20)

    example_list = [alice, bob, clementine, dave]
    example_deck = Deck()
    example_hand = Hand(example_list, 0, 3, 1, 2, 0, example_deck)

    example_hand.run_hand()