from player import Player
from chip_stack import ChipStack
from treys import Card, Deck, Evaluator
from agents.input_agent import InputAgent
from copy import deepcopy


class InvalidStringError(Exception):
    """Raised when an invalid or illegal string is found."""
    pass


class Hand:
    def __init__(
            self,
            player_list: list[Player],
            hand_id: int,
            round_id: int,
            ante: int,
            small_blind: int,
            big_blind: int,
            deck: Deck
    ):
        assert 2 <= len(player_list) <= 10
        assert len(player_list) == len(set(player_list)) # No duplicated players
        self.player_list = player_list
        self.hand_id = hand_id
        self.round_id = round_id
        self.ante = ante
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.deck = deck
        self.community_cards = []
        self.pot_stacks = []
        self.evaluator = Evaluator()
        self.hand_log = []
        main_pot = {
            'stack': ChipStack(),
            'eligible_players': self.player_list.copy()
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
            to_str = Card.ints_to_pretty_str(hole_cards)
            print(f"Dealt hole cards to {self.player_list[index]}: {to_str}")
            index += 1
            if index == len(self.player_list):
                index = 0

    def deal_community_cards(self, amount: int):
        """Deals community cards."""
        if amount < 0:
            raise ValueError("Cannot deal negative amount of community cards")
        self.community_cards = self.community_cards + self.deck.draw(amount)
        to_str = Card.ints_to_pretty_str(self.community_cards)
        print(f"All community cards: {to_str}")

    def log(self, player: Player, stack_before: int, action: str, cost: int, stage: str):
        if action not in ['ante', 'small-blind', 'big-blind', 'bet', 'check', 'fold', 'call', 'raise', 'all-in']:
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

    def get_stage_name(self):
        stages = {0: 'pre-flop', 3: 'flop', 4: 'turn', 5: 'river'}
        current_stage = stages[len(self.community_cards)]
        return current_stage

    def get_player_status(self, player: Player):
        player_status = {
            'position': self.player_list.index(player),
            'player_id': player.player_id,
            'stack': player.stack.amount,
            'hand_status': player.hand_status,
            'current_bet_this_stage': player.unresolved_chips,
            'total_bet_this_hand': player.total_bet_this_hand
        }
        return player_status

    def get_game_state(self, player: Player, stack: ChipStack, bet_to_call: int, min_raise: int):
        current_stage = self.get_stage_name()

        hole_cards = []
        for hole_card in player.hole_cards:
            hole_cards.append(Card.int_to_str(hole_card))

        community_cards = []
        for community_card in self.community_cards:
            community_cards.append(Card.int_to_str(community_card))

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

        current_stage_logs = [
            log for log in self.hand_log
            if log['stage'] == current_stage
        ]
        # n = len(self.player_list)
        # recent_history = current_stage_logs[-n:]

        game_state = {
            # --- PRIVATE INFO (Only this player sees this) ---
            "hole_cards": hole_cards,  # Your 2 cards

            # --- PUBLIC SHARED INFO ---
            "hand_id": self.hand_id,
            "round_id": self.round_id,
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
            "small_blind": self.small_blind,        # Reference for sizing bets
            "big_blind": self.big_blind,            # Reference for sizing bets
            "ante": self.ante,                      # Reference for sizing bets

            # --- PLAYER STATUS ---
            # A list of everyone at the table (ordered by position)
            "players": players,

            # --- ACTION HISTORY (Crucial for detecting logic) ---
            # A list of sequential actions in the current hand
            "hand_log": current_stage_logs
        }

        isolated_state = deepcopy(game_state)

        return isolated_state

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
            if pot_increase == 0:
                # Current pot will be empty, remove it
                assert self.pot_stacks[-1]['stack'].amount == 0
                self.pot_stacks.pop()
            else:
                # Current pot will not be empty, add chips to it
                for player in non_all_iners + all_iners + [least_committed]:
                    amount = min(pot_increase, player.unresolved_chips)
                    self.pot_stacks[-1]['stack'].add(stack.pop(amount))
                    player.resolve(amount)

            # Create a new side pot that excludes this player
            new_side_pot = {
                'stack': ChipStack(),
                'eligible_players': non_all_iners + all_iners
            }
            self.pot_stacks.append(new_side_pot)

        # For players who don't all-in just move their chips to the current pot
        for player in non_all_iners:
            self.pot_stacks[-1]['stack'].add(stack.pop(player.unresolved_chips))
            player.resolve(player.unresolved_chips)

        assert stack.amount == 0
        print(self.pot_stacks)

    def get_max_bet(self):
        return max(p.unresolved_chips for p in self.player_list)

    def betting_stage(self, stack: ChipStack, current_player: int, bet_to_call: int, min_raise: int):
        if len(self.get_active_players()) < 2:
            return
        retry_count = 0     # Times failed to find the next active player
        while retry_count < len(self.player_list) - 1:
            # Pick the next player in order
            player = self.player_list[current_player]
            actable = player.is_actable(bet_to_call)
            if actable:

                game_state = self.get_game_state(player, stack, bet_to_call, min_raise)
                action = self.player_list[current_player].decide_action(game_state)
                stack_before = player.stack.amount
                bet_to_call_before = bet_to_call
                cost = 0
                action_name = 'none'

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
                self.log(player, stack_before, action_name, cost, self.get_stage_name())

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
        competing_players = self.get_competing_players()
        assert len(competing_players) > 0

        if len(competing_players) == 1:
            winner = competing_players[0]
            while self.pot_stacks:
                pot = self.pot_stacks.pop()
                if pot['stack'].amount == 0:
                    continue
                assert winner in pot['eligible_players']
                winner.stack.add(pot['stack'].pop(pot['stack'].amount))
            # Log the win
            print(f"Hand ended. {winner} wins by everyone else folding")

            return True

        return False

    def collect_antes(self):
        stack = ChipStack()

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

    def run_preflop(self):
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

        # Start Pre-flop betting stage
        current_player = utg
        bet_to_call = self.big_blind    # During Pre-flop, min bet to call = big blind, no matter how much the BB paid
        min_raise = self.big_blind
        self.betting_stage(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_flop(self):
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 3 community cards
        self.deal_community_cards(3)

        # Start Flop betting stage
        current_player = sb # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_stage(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_turn(self):
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 1 community card
        self.deal_community_cards(1)

        # Start Turn betting stage
        current_player = sb  # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_stage(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def run_river(self):
        stack = ChipStack()
        _, sb, _, _ = self.get_positions()

        for player in self.player_list:
            player.stage_start()

        # Deal 1 community card
        self.deal_community_cards(1)

        # Start River betting stage
        current_player = sb  # Starts with the SB and find the next active player
        bet_to_call = 0
        min_raise = self.big_blind
        self.betting_stage(stack, current_player, bet_to_call, min_raise)

        self.add_to_pots(stack)

    def showdown(self):
        assert len(self.community_cards) == 5
        competing_players = self.get_competing_players()
        assert len(competing_players) > 1

        while self.pot_stacks:
            pot = self.pot_stacks.pop()
            if pot['stack'].amount == 0:
                continue
            eligible_players = list(set(competing_players) & set(pot['eligible_players']))
            player_scores = []
            for player in eligible_players:
                assert len(player.hole_cards) == 2
                score = self.evaluator.evaluate(player.hole_cards, self.community_cards)
                player_scores.append((player, score))
            player_scores.sort(key=lambda x: x[1])
            best_score = player_scores[0][1]
            winners = [p for p, score in player_scores if score == best_score]
            pot_amount = pot['stack'].amount
            num_winners = len(winners)
            split_amount = pot_amount // num_winners
            odd_chips = pot_amount % num_winners

            for winner in winners:
                winner.stack.add(pot['stack'].pop(split_amount))
                print(f"{winner.name} wins {split_amount} from the pot")

            if odd_chips > 0:
                print(f"Distributing {odd_chips} odd chips...")
                _, index, _, _ = self.get_positions()
                while odd_chips:
                    player = self.player_list[index]
                    if player in winners:
                        player.stack.add(pot['stack'].pop(1))
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
                return  # Exit run_hand immediately

        # If we survive all stages without a fold-win, it's a showdown
        self.showdown()


if __name__ == '__main__':
    alice = Player(0, InputAgent(), "Alice")
    bob = Player(1, InputAgent(), "Bob")
    clementine = Player(2, InputAgent(), "Clementine")
    dave = Player(3, InputAgent(), "Dave")

    alice.stack.add(20)
    bob.stack.add(9)
    clementine.stack.add(20)
    dave.stack.add(20)

    example_list = [alice, bob, clementine, dave]
    example_deck = Deck()
    example_hand = Hand(example_list, 0, 0, 3, 1, 2, example_deck)

    example_hand.run_hand()
    for example_player in example_list:
        print(example_player, example_player.stack)
    print(example_hand.hand_log)