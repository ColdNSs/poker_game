from .base_agent import BasePokerAgent
import sys

def prompt_confirm(prompt: str = None):
    if prompt is None:
        prompt = "Press enter to continue..."
    input(prompt)

def get_positions(n: int):
    """Yields indexes of Dealer, Small Blind, Big Blind and Under the Gun."""

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

def box_padding(pretty_list: list, highlighted: bool = False, boundary_char: str = "*"):
    longest_item = max(pretty_list, key=len)
    padding_to = max(len(longest_item) + 2, 22)
    padded_list = []
    for item in pretty_list:
        short = padding_to - len(item)
        even_padding = short // 2
        odd_padding = short % 2
        item = even_padding * " " + item + even_padding * " "
        if odd_padding:
            item = " " + item
        item = item + boundary_char
        padded_list.append(item)

    top_boundary_char = boundary_char if highlighted else " "
    top_padding = padding_to * top_boundary_char + boundary_char
    padded_list.insert(0, top_padding)
    padded_list.append(top_padding)

    return padded_list

def splice(pretty_lists: list[list], boundary_char: str = "*"):
    longest_item = max(pretty_lists, key=len)
    total_items = len(longest_item)
    spliced_list = []
    for i in range(total_items):
        spliced_list.append(boundary_char)
        for item in pretty_lists:
            spliced_list[i] = spliced_list[i] + item[i]
    return spliced_list

def pretty_card(card: str) -> str:
    """
    Convert poker card string like 'As', 'Th', '9d'
    into colored string with Unicode suit.
    """

    if len(card) != 2:
        raise ValueError("Card must be 2 characters like 'As', 'Th', '9d'")

    rank = card[0]
    suit = card[1].lower()

    suits = {
        's': ('♠', 30),  # black
        'h': ('♥', 31),  # red
        'd': ('♦', 33),  # yellow
        'c': ('♣', 34),  # blue
    }

    if suit not in suits:
        raise ValueError("Invalid suit. Use s, h, d, or c.")

    symbol, color_code = suits[suit]

    return f"\033[{color_code}m[{rank}{symbol}]\033[0m"


class InputAgent(BasePokerAgent):
    def __init__(self, seed: int = None, name: str = "Input Agent", dollar_per_chip: int = 5, player_names: dict = None):
        if dollar_per_chip < 1:
            raise ValueError("Dollar to chip ratio should at least be 1")
        if player_names is None:
            player_names = dict()
        super().__init__(seed, name)
        self.dollar_per_chip = dollar_per_chip
        # Game state does not contain player names, only player ids. Pass a dictionary if you want readability
        self.player_names = player_names

    def chip2dollar(self, amount: int) -> str:
        if amount < 0:
            raise ValueError("Cannot convert negative amount of chips")
        return f"${self.dollar_per_chip * amount}"

    # Someone please move this monstrosity somewhere else
    def pick_commentary(self,
                        total_bet_this_hand: int,
                        winnings: int,
                        stack: int,
                        hand_status: str,
                        end_at: str) -> str:
        random = self._random
        net = winnings - total_bet_this_hand

        won = net > 0
        lost = net < 0
        showdown = end_at == "showdown"

        # --- WIN CASE ---
        if won:
            pretty_gain = self.chip2dollar(winnings)
            if showdown:
                lines = [
                    f"You take it all the way to showdown and are rewarded with {pretty_gain}!",
                    f"You show down the best hand and collect {pretty_gain} for your patience!",
                    f"You trusted your hand to the end, and it pays off with {pretty_gain}!",
                    f"You let the cards speak at showdown and they speak in your favor!",
                ]
            else:
                lines = [
                    f"You apply pressure and everyone folds. {pretty_gain} gained without a showdown!",
                    f"You take it down on the {end_at.capitalize()} and collect {pretty_gain} uncontested!",
                    f"You didn’t need to show your cards. The {pretty_gain} pot slides your way!",
                    f"You push them out before showdown and quietly stack {pretty_gain}!",
                ]

            # Big win variation
            if net > total_bet_this_hand * 3:
                lines += [
                    f"You turned that into a massive score. That one changes stacks.",
                    f"You didn’t just win — you made a statement.",
                ]

            return random.choice(lines)

        # --- LOSS CASE ---
        if lost:
            loss = -net
            pretty_loss = self.chip2dollar(loss)

            if stack == 0:
                lines = [
                    f"And that’s it. You’re out. No chips. No comeback. Just a long walk away from the table.",
                    f"Your stack hits zero. The tournament continues — without you.",
                    f"You fought. You gambled. You’re gone.",
                    f"The last chip slides away, and so do you.",
                ]

            elif showdown and hand_status == 'active':
                lines = [
                    f"Better luck next time.",
                    f"You make it to showdown, but your hand comes up short.",
                    f"You pay to see it and pay the price. Your {pretty_loss} must be missing you.",
                    f"You go the distance, only to watch {pretty_loss} slide away.",
                    f"You show your cards — and wish you hadn’t. That's {pretty_loss} less for you.",
                ]

            elif showdown:
                lines = [
                    f"You commit {pretty_loss} this hand and don’t get them back.",
                    f"You invest {pretty_loss}, but this one doesn’t go your way.",
                    f"You put {pretty_loss} into the middle and they stay there.",
                    f"You take a shot and it costs you {pretty_loss}.",
                    f"You step away from the pot, down {pretty_loss} this hand.",
                    f"You test the waters and retreat, {pretty_loss} lighter.",
                ]

            else:
                lines = [
                    f"You invest {pretty_loss} but can’t continue on the {end_at.capitalize()}.",
                    f"You let it go before showdown, leaving your {pretty_loss} behind.",
                    f"You step away from the pot, down {pretty_loss} this hand.",
                    f"You test the waters and retreat, {pretty_loss} lighter.",
                ]

            return random.choice(lines)

        # --- BREAK EVEN ---
        lines = [
            "You navigate the hand carefully and come out exactly where you started.",
            "No harm done. Your stack remains unchanged.",
            "You get involved, but the dust settles with no chips gained or lost.",
            "A neutral result — you live to fight the next hand.",
        ]

        return random.choice(lines)

    def pretty_player_name(self, player_id: int):
        player_name = self.player_names.get(player_id)
        if not player_name:
            player_name = f"#{player_id}"
        return player_name

    def pretty_player_names(self, player_ids: list[int]):
        pretty_str = ""
        for player_id in player_ids:
            pretty_str = pretty_str + f"#{self.pretty_player_name(player_id)}, "
        pretty_str = pretty_str.rstrip(", ")
        return pretty_str

    def pretty_players(self, your_id: int, players, logs, boundary_char: str = "*"):
        dealer, sb ,bb, _ = get_positions(len(players))
        cost_action = ['ante',
                        'small-blind',
                        'big-blind',
                        'bet',
                        'call',
                        'raise',
                        'all-in']

        pretty_status = []
        for player_status in players:
            player_id = player_status['player_id']
            pretty_id = f"{self.pretty_player_name(player_id)}"

            position = player_status['position']
            pretty_position = ""
            if position == dealer:
                pretty_position = pretty_position + "Dealer/"
            if position == sb:
                pretty_position = pretty_position + "Small Blind/"
            if position == bb:
                pretty_position = pretty_position + "Big Blind/"
            pretty_position = pretty_position.rstrip('/')
            if pretty_position:
                pretty_position = f"({pretty_position})"

            stack = player_status['stack']
            pretty_stack = f"Stack {self.chip2dollar(stack)}"

            recent_action = None
            for item in reversed(logs):
                if item['player_id'] == player_id:
                    recent_action = item
                    break
            pretty_action = ""
            if player_status['hand_status'] == 'all-in':
                pretty_action = "All-in"
            if player_status['hand_status'] == 'folded':
                pretty_action = "Folded"
            if recent_action:
                action_name = recent_action['action']
                pretty_action_name = action_name.capitalize()
                if action_name in cost_action:
                    cost = recent_action['cost']
                    pretty_cost = self.chip2dollar(cost)
                    pretty_action = f"{pretty_action_name} {pretty_cost}"
                else:
                    pretty_action = pretty_action_name

            pretty_list = [pretty_id, pretty_position, pretty_stack, pretty_action]
            highlighted = True if your_id == player_id else False
            padded_list = box_padding(pretty_list, highlighted, boundary_char)
            pretty_status.append(padded_list)

        spliced_status = splice(pretty_status, boundary_char)
        return spliced_status

    def pretty_player_results(self,  your_id: int, player_results, boundary_char: str = "*"):
        pretty_results = []
        list_to_replace = []

        for player in player_results:
            player_id = player['player_id']
            pretty_id = f"{self.pretty_player_name(player_id)}"

            hole_cards = player['hole_cards']
            pretty_hole_cards = ""
            if hole_cards:
                for card in hole_cards:
                    pretty_hole_cards = pretty_hole_cards + f" [{card}]"
                    list_to_replace.append(card)

            stack = player['stack']
            pretty_stack = f"Stack {self.chip2dollar(stack)}"

            gain = player['winnings']
            if stack == 0:
                pretty_gain = f"( Eliminated )"
            elif gain:
                pretty_gain = f"( +{self.chip2dollar(gain)} )"
            else:
                pretty_gain = ""

            pretty_list = [pretty_id, pretty_hole_cards, pretty_stack, pretty_gain]
            highlighted = True if your_id == player_id else False
            padded_list = box_padding(pretty_list, highlighted, boundary_char)
            pretty_results.append(padded_list)

        spliced_results = splice(pretty_results, boundary_char)
        for card in list_to_replace:
            spliced_results[2] = spliced_results[2].replace(f"[{card}]", pretty_card(card))
        return spliced_results

    def pretty_print_game_state(self, game_state: dict):
        pretty_print = ["------ GAME STATE ------"]

        hand_id = game_state['hand_id']
        ante = game_state['ante']
        small_blind = game_state['small_blind']
        big_blind = game_state['big_blind']
        your_id = game_state['your_status']['player_id']
        pretty_print.append(f"[ Hand {hand_id} / "
                            f"Ante {self.chip2dollar(ante)} / "
                            f"Small Blind {self.chip2dollar(small_blind)} / "
                            f"Big Blind {self.chip2dollar(big_blind)} ] "
                            f"You are playing as {self.pretty_player_name(your_id)}")

        players = game_state['players']
        logs = game_state['hand_log']
        pretty_players = self.pretty_players(your_id, players, logs)
        pretty_print = pretty_print + pretty_players

        stage_pot = game_state['stage_pot']
        pots = game_state['pots']

        pretty_pots = f" | Stage Pot {self.chip2dollar(stage_pot)}"
        total_pot = stage_pot
        for index, pot in enumerate(pots):
            stack = pot['amount']
            eligible_players = pot['eligible_players']

            # When it's the main pot
            if index == 0:
                pretty_pots = pretty_pots + f" | Main Pot {self.chip2dollar(stack)}"
            # When it's a side pot
            else:
                pretty_eligibles = self.pretty_player_names(eligible_players)
                pretty_pots = pretty_pots + f" | Side Pot {self.chip2dollar(stack)} ({pretty_eligibles})"
            total_pot += stack
        pretty_pots = f"Total Pot {self.chip2dollar(total_pot)}" + pretty_pots
        pretty_print.append(pretty_pots)

        pretty_community = f"{game_state['current_stage'].capitalize()}"
        community_cards = game_state['community_cards']
        if community_cards:
            pretty_community = pretty_community + ": "
            for card in community_cards:
                pretty_community = pretty_community + f"{pretty_card(card)} "
        pretty_print.append(pretty_community)

        pretty_hole = f"Your private cards: "
        for card in game_state['hole_cards']:
            pretty_hole = pretty_hole + f"{pretty_card(card)} "
        pretty_print.append(pretty_hole)

        bet_to_call = game_state['bet_to_match']
        if bet_to_call == 0:
            pretty_cost = f"Check to stay in the hand. "\
                          f"Or bet at least {self.chip2dollar(game_state['min_cost_to_increase'])}."
        else:
            pretty_cost = f"Spend {self.chip2dollar(game_state['cost_to_match'])} to call. "\
                          f"Or spend at least {self.chip2dollar(game_state['min_cost_to_increase'])} to raise."
        pretty_print.append(pretty_cost)

        for item in pretty_print:
            print(item)

    def pretty_print_hand_history(self, hand_history):
        pretty_print = ["------ HAND HISTORY ------"]

        hand_id = hand_history['hand_id']
        ante = hand_history['ante']
        small_blind = hand_history['small_blind']
        big_blind = hand_history['big_blind']
        your_id = hand_history['your_result']['player_id']
        pretty_print.append(f"[ Hand {hand_id} / "
                            f"Ante {self.chip2dollar(ante)} / "
                            f"Small Blind {self.chip2dollar(small_blind)} / "
                            f"Big Blind {self.chip2dollar(big_blind)} ] "
                            f"You are playing as {self.pretty_player_name(your_id)}")

        player_results = hand_history['player_results']
        pretty_results = self.pretty_player_results(your_id, player_results)
        pretty_print = pretty_print + pretty_results

        pretty_print.append(f"Hand ended.")

        end_at = hand_history['end_at']
        pretty_community = f"{end_at.capitalize()}"
        community_cards = hand_history['community_cards']
        if community_cards:
            pretty_community = pretty_community + ": "
            for card in community_cards:
                pretty_community = pretty_community + f"{pretty_card(card)} "
        pretty_print.append(pretty_community)

        total_bet_this_hand = hand_history['your_result']['total_bet_this_hand']
        winnings = hand_history['your_result']['winnings']
        stack = hand_history['your_result']['stack']
        hand_status = hand_history['your_result']['hand_status']
        commentary = self.pick_commentary(total_bet_this_hand, winnings, stack, hand_status, end_at)
        pretty_print.append(commentary)

        for item in pretty_print:
            print(item)

        prompt_confirm()

    def game_start(self, start_state):
        print(start_state)

    def decide_action(self, game_state: dict):
        self.pretty_print_game_state(game_state)
        valid_actions = ('match', 'increase', 'fold')
        action = ''
        amount = 0
        while action not in valid_actions:
            cmd = input("Input your action (match/increase/fold): ")
            to_list = cmd.split(' ')
            action = to_list[0]

            # Resolve alias
            if action in ['check', 'call']:
                action = 'match'
            elif action in ['bet', 'raise']:
                action = 'increase'

            if action == 'increase':
                if len(to_list) > 1:
                    amount = to_list[1]
                    if amount.isdigit():
                        amount = abs(int(amount)) // self.dollar_per_chip
                if not amount:
                    action = ''

            if action == 'all-in':
                action = 'increase'
                amount = game_state['your_status']['stack']

        return {'action': action, 'amount': amount}

    def hand_ended(self, hand_history):
        self.pretty_print_hand_history(hand_history)

if __name__ == '__main__':
    example_agent = InputAgent()
    example_players = [{'position': 0, 'player_id': 0, 'stack': 7, 'hand_status': 'active', 'current_bet_this_stage': 0, 'total_bet_this_hand': 3}, {'position': 1, 'player_id': 1, 'stack': 5, 'hand_status': 'active', 'current_bet_this_stage': 1, 'total_bet_this_hand': 4}, {'position': 2, 'player_id': 2, 'stack': 5, 'hand_status': 'active', 'current_bet_this_stage': 2, 'total_bet_this_hand': 5}, {'position': 3, 'player_id': 3, 'stack': 7, 'hand_status': 'active', 'current_bet_this_stage': 0, 'total_bet_this_hand': 3}]
    example_logs = [{'player_id': 1, 'stack_before': 6, 'action': 'small-blind', 'cost': 1, 'stage': 'pre-flop'}, {'player_id': 2, 'stack_before': 7, 'action': 'big-blind', 'cost': 2, 'stage': 'pre-flop'}]
    example_agent.pretty_players(0, example_players, example_logs)