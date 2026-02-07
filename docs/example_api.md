# Example API

Agent class:
```python
from random import Random


class BasePokerAgent:
    def __init__(self, name, seed):
        self.name = name
        self._random = Random(seed)

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

Game state:
```python
game_state = {
    # --- PRIVATE INFO (Only this player sees this) ---
    "hole_cards": ['As', 'Ts'],  # Your 2 cards

    # --- PUBLIC SHARED INFO ---
    "hand_id": 0,
    "current_active_players": [2, 0, 1], # Active players in order
    "community_cards": ['2h', '5d', '9s'], # Empty [] pre-flop
    "current_stage": "flop",   # "pre-flop", "flop", "turn", "river"
    "pots": [
        {
            "pot_id": 0,
            "amount": 100,          # Total chips in this pot
            "eligible_players": [0,1,2]  # Player IDs who can win this pot
        },
        {
            "pot_id": 1,
            "amount": 50,
            "eligible_players": [0,2]    # Players not all-in
        }
    ],

    # --- BETTING MATH ---
    "to_call": 20,             # Cost to stay in hand (0 means you can Check)
    "min_raise": 40,           # Minimum total bet amount if you want to raise
    "big_blind": 20,           # Reference for sizing bets
    "ante": 10,                # Reference for sizing bets

    # --- PLAYER STATUS ---
    "your_id": 0,
    # A list of everyone at the table (ordered by position relative to button)
    "players": [
        {
            "agent_id": 0,
            "stack": 900,
            "status": "active",      # "active", "folded", "all-in"
            "position": 0,        # 0 (Dealer), 1 (Small Blind), 2 (Big Blind), 3 (Under the Gun), 4...
            "current_bet_this_round": 20, # How much they put in this specific street
            "total_bet_this_hand": 50
        },
        # ... other players
    ],

    # --- ACTION HISTORY (Crucial for detecting logic) ---
    # A list of sequential actions in the current hand
    "hand_log": [
        {"agent_id": 1, "stack_before": 900, "action": "bet", "amount": 10, "stage": "pre-flop"},
        {"agent_id": 2, "stack_before":850, "action": "raise", "amount": 30, "stage": "pre-flop"},
    ]
}
```

Hand history:
```python
hand_history = {
    "community_cards": ['2h', '5d', '9s'],
    "showdown_data": {
        0: 
        {
            "hole_cards": ['Ah', 'Kh'],
            "hand_rank": 123123123,
            "winning_pots": [0, 1]
        },
        1: 
        {
            "hole_cards": ['2c', '7d'],
            "hand_rank": 123123123,
            "winning_pots": None
        },
        2:
        {
            "hole_cards": None,
            "hand_rank": None,
            "winning_pots": None
        }, # Folded earlier, cards remain a mystery
    },
    "full_action_log": [...] # Complete list of every bet/check this hand
}
```