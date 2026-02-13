from .base_agent import BasePokerAgent

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

def pretty_player_ids(player_ids: list[int]):
    pretty_str = ""
    for player_id in player_ids:
        pretty_str = pretty_str + f"#{player_id}" + ", "
    pretty_str = pretty_str.rstrip(", ")
    return pretty_str

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
    def __init__(self, seed: int = None, name: str = "Input Agent", dollar_per_chip: int = 5):
        if dollar_per_chip < 1:
            raise ValueError("Dollar to chip ratio should at least be 1")
        super().__init__(seed, name)
        self.dollar_per_chip = dollar_per_chip

    def chip2dollar(self, amount: int) -> str:
        if amount < 0:
            raise ValueError("Cannot convert negative amount of chips")
        return f"${self.dollar_per_chip * amount}"

    def pretty_str_players(self, your_id: int, players, logs, boundary_char: str = "*"):
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
            pretty_id = f"#{player_id}"

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
            if player_status['hand_status'] == 'fold':
                pretty_action = "Fold"
            elif recent_action:
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

    def pretty_print_game_state(self, game_state: dict):
        pretty_print = [""]

        hand_id = game_state['hand_id']
        round_id = game_state['round_id']
        your_id = game_state['your_status']['player_id']
        pretty_print.append(f"[ Hand {hand_id} / Round {round_id} ] You are playing as #{your_id}")

        players = game_state['players']
        logs = game_state['hand_log']
        pretty_players = self.pretty_str_players(your_id, players, logs)
        pretty_print = pretty_print + pretty_players

        stage_pot = game_state['stage_pot']
        pots = game_state['pots']

        pretty_pots = f"Stage Pot {self.chip2dollar(stage_pot)}"
        for index, pot in enumerate(pots):
            stack = pot['amount']
            eligible_players = pot['eligible_players']
            pretty_pots = pretty_pots + " | "

            # When it's the main pot
            if index == 0:
                pretty_pots = pretty_pots + f"Main Pot {self.chip2dollar(stack)}"
            # When it's a side pot
            else:
                pretty_eligibles = pretty_player_ids(eligible_players)
                pretty_pots = pretty_pots + f"Side Pot {self.chip2dollar(stack)} ({pretty_eligibles})"
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
            pretty_cost = f"Check to stay in the hand. Or bet at least {self.chip2dollar(game_state['min_cost_to_increase'])}."
        else:
            pretty_cost = f"Spend {self.chip2dollar(game_state['cost_to_match'])} to call. Or spend at least {self.chip2dollar(game_state['min_cost_to_increase'])} to raise."
        pretty_print.append(pretty_cost)

        for item in pretty_print:
            print(item)

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

        return {'action': action, 'amount': amount}

    def hand_ended(self, hand_history):
        print(hand_history)

if __name__ == '__main__':
    example_agent = InputAgent()
    example_players = [{'position': 0, 'player_id': 0, 'stack': 7, 'hand_status': 'active', 'current_bet_this_stage': 0, 'total_bet_this_hand': 3}, {'position': 1, 'player_id': 1, 'stack': 5, 'hand_status': 'active', 'current_bet_this_stage': 1, 'total_bet_this_hand': 4}, {'position': 2, 'player_id': 2, 'stack': 5, 'hand_status': 'active', 'current_bet_this_stage': 2, 'total_bet_this_hand': 5}, {'position': 3, 'player_id': 3, 'stack': 7, 'hand_status': 'active', 'current_bet_this_stage': 0, 'total_bet_this_hand': 3}]
    example_logs = [{'player_id': 1, 'stack_before': 6, 'action': 'small-blind', 'cost': 1, 'stage': 'pre-flop'}, {'player_id': 2, 'stack_before': 7, 'action': 'big-blind', 'cost': 2, 'stage': 'pre-flop'}]
    example_agent.pretty_str_players(0, example_players, example_logs)