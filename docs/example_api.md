# Example API

Agent class:
```python
from random import Random


class BasePokerAgent:
    def __init__(self, seed: int = None, name: str = "Base Agent"):
        self.name = name
        self.seed = None
        self._random = None
        self.init_seed(seed)

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
```

Game Start:
```python
start_state = {
    "initial_stack_per_player": 1000,
    "player_count": 8,
    "your_status": {
        "player_id": 2,
        "stack": 1000,
        "order": 0, # Game plays clockwise 0 -> 1 -> 2 -> 3 -> ... -> 0
    },
    "players": [
        {
            "player_id": 2,
            "stack": 1000,
            "order": 0, # Game plays clockwise 0 -> 1 -> 2 -> 3 -> ... -> 0
        },
        # ... other players
    ],
}
```

Game state:
```python
game_state = {
    # --- PRIVATE INFO (Only this player sees this) ---
    "hole_cards": ['As', 'Ts'],  # Your 2 cards

    # --- PUBLIC SHARED INFO ---
    "hand_id": 0,
    "community_cards": ['2h', '5d', '9s'], # Empty [] pre-flop
    "current_stage": "flop",   # "pre-flop", "flop", "turn", "river"
    "pots": [
        {
            "amount": 100,          # Total chips in this pot
            "eligible_players": [0,1,2]  # Player IDs who can win this pot
        },
        {
            "amount": 50,
            "eligible_players": [0,2]    # Players not all-in
        }
    ],

    # --- YOUR STATUS ---
    "your_status": {
        "position": 0,  # Play order THIS hand. Dealer button moves every hand. 0 (Dealer), 1 (Small Blind), 2 (Big Blind), 3 (Under the Gun), 4...
        "player_id": 0,
        "stack": 900,
        "hand_status": "active",  # "active", "folded", "all-in"
        "current_bet_this_stage": 20,  # How much they put in this betting round
        "total_bet_this_hand": 50,
        "can_raise": True
    },
    
    # --- BETTING MATH ---
    "bet_to_match": 70,  # Bet you have to match if you want to check or call
    "min_increase": 50,  # Minimum amount to increase by if you want to bet or raise
    "cost_to_match": 50, # How much you have to pay if you want to check or call
    "min_cost_to_increase": 100, # How much at least you have to pay if you want to bet or raise
    "small_blind": 10, # Reference for sizing bets
    "big_blind": 20,  # Reference for sizing bets
    "ante": 10,  # Reference for sizing bets

    # --- PLAYER STATUS ---
    # A list of everyone at the table (ordered by position)
    "players": [
        {
            "position": 0,        # Play order THIS hand. Dealer button moves every hand. 0 (Dealer), 1 (Small Blind), 2 (Big Blind), 3 (Under the Gun), 4...
            "player_id": 0,
            "stack": 900,
            "hand_status": "active",      # "active", "folded", "all-in"
            "current_bet_this_stage": 20, # How much they put in this betting round
            "total_bet_this_hand": 50,
            "can_raise": True
        },
        # ... other players
    ],

    # --- ACTION HISTORY (Crucial for detecting logic) ---
    # A list of sequential actions in the current hand
    "hand_log": [
        {"player_id": 1, "stack_before": 900, "action": "bet", "cost": 20, "stage": "pre-flop"},
        {"player_id": 2, "stack_before":850, "action": "raise", "cost": 30, "stage": "pre-flop"},
    ]
}
```

Hand history:
```python
hand_history = {
    "hand_id": 0,
    "small_blind": 10,
    "big_blind": 20,
    "ante": 10,
    "community_cards": ['2h', '5d', '9s'],
    "end_at": "showdown",
    "your_result": {
        "player_id": 0,
        "hand_status": "active",
        "hole_cards": ['Ah', 'Kh'],
        "score": 123123123, # Score evaluated by treys. Lower score means better hand
        "total_bet_this_hand": 1200, # Chips spent
        "winnings": 3600, # Chips gained
        "stack": 2200, # Stack after this hand
        "rank": None # When player is still alive
    },
    "player_results": [
        {
            "player_id": 0,
            "hand_status": "active",
            "hole_cards": ['Ah', 'Kh'],
            "score": 123123123, # Score evaluated by treys. Lower score means better hand
            "total_bet_this_hand": 1200, # Chips spent
            "winnings": 3600, # Chips gained
            "stack": 2200, # Stack after this hand
            "rank": None # When player is still alive
        },
        {
            "player_id": 1,
            "hand_status": "all-in",
            "hole_cards": ['2c', '7d'],
            "score": 123123123,
            "total_bet_this_hand": 1200, # Chips spent
            "winnings": 0, # Chips gained
            "stack": 0, # Player is eliminated when stack is reduced to 0
            "rank": 3 # When player is eliminated
        },
        {
            "player_id": 2,
            "hand_status": "active",
            "hole_cards": None, # Folded earlier, cards remain a mystery
            "score": None,
            "total_committed": 1200, # Chips spent
            "winnings": 0, # Chips gained
            "stack": 500,
            "rank": None
        }, 
    ],
    "full_action_log": [...] # Complete list of every bet/check this hand
}
```