You are a professional software engineer and a professional No-Limit Texas Hold’em tournament player.
You are participating in a serious high-stakes tournament simulation. The prize is worth one million dollars. Your reputation and career depend on your performance.

You will face:
- Other AI-generated strategies
- Unknown opponent strategies
- Strong human-designed strategies
- Real human players that adapt depending on the situation

Your only objective is:
- Maximize final ranking in each game.

Chip EV alone is not enough.
Survival, stack growth timing, blind pressure, and adaptation to different opponent types all matter.
You are playing to **WIN** the tournament — not to look balanced, not to appear fair, and not to be “nice”.

You must design and implement a complete poker strategy under the following constraints:

---

#### Technical Constraints
1. You must write in Python 3.11.
2. You will be given an API. You must strictly follow it.
3. Use `BasePokerAgent` as the parent class. Use `from .base_agent import BasePokerAgent` to import it.
4. No machine learning.
   - No neural networks
   - No training loops
   - No external models
   - Strategy must be fully interpretable and deterministic (except controlled randomness).
5. If you use randomness:
   - You MUST use the randomness provided by the API.
   - You must NEVER use global randomness (e.g., random.random() without the provided instance).
   - This is to make sure that the result is reproducible using the same seed.
6. You may import utility libraries (e.g., math, dataclasses, typing, collections). However:
   - You may NOT import any poker-solving libraries.
   - You may NOT use prebuilt poker strategies.
7. No online search or retrieval.
Strategy must be derived from your own **reasoning**, not copied charts.

#### Strategic Expectations
You are not writing a beginner bot.
Think like a tournament professional:
- Stack depth awareness
- Blind and ante pressure
- Risk-adjusted aggression
- Positional advantage
- Opponent modeling
- Exploitative adjustments
- All-in dynamics
- Short stack push/fold logic
- Deep stack postflop logic
- Pot odds and implied odds
- Minimum defense frequency concepts

Your strategy should:
- Adapt across early, mid, and late stages
- Adjust aggression based on stack size
- Recognize when survival is more important than marginal EV
- Punish overly tight or overly loose opponents
- Avoid being trivially exploitable by simple bots (e.g., always-all-in bots)

You are allowed to:
- **Reason Heavily** before outputting any code
- Use structured heuristics
- Implement rule-based systems
- Use mathematical thresholds
- Implement equilibrium-inspired logic
- Use parameterized aggression logic
- But everything must be explainable by reading the code.
- Output Requirements
- Output valid Python 3.11 code.
- Provide explanations inside comments.
- The code must be clean, structured, and modular.
- Use clear function decomposition where appropriate.
- Use comments to explain reasoning behind major strategic decisions.
- Follow the provided API exactly.
- Do not modify the API.

You are competing against other highly intelligent agents.
Design a strategy that you believe can consistently achieve top placements in a strong tournament field.

Below is the API you must use:

Base Agent class:
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
        You may use this to create an internal database.
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
        You may use this to update your internal database of opponent tendencies.
        """
        pass
```

Action:
```python
"""
Check / Call -> match
Bet / Raise -> increase
Fold -> fold

When you choose to match, the engine will automatically spend chips for you, you can leave the amount empty. The actual amount will be `cost_to_match`.
When you choose to increase, you MUST provide the amount you want to SPEND (that includes the call part). The amount should be at least `min_cost_to_increase`.
When you have insufficient money, the engine will handle all-in automatically.
"""
action = {
    "action": "increase", # match, increase, fold
    "amount": 150
}
```

Game Start:
```python
start_state = {
    "initial_stack_per_player": 2000,
    "player_count": 8,
    "level_one_big_blind": 20,
    "your_status": {
        "player_id": 2,
        "stack": 2000,
        "order": 4, # Game plays clockwise 0 -> 1 -> 2 -> 3 -> ... -> 0
    },
    # Your status is also included in all player status
    "players": [
        {
            "player_id": 1,
            "stack": 2000,
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
    "hole_cards": ['As', 'Ts'], # Your 2 cards

    # --- PUBLIC SHARED INFO ---
    "hand_id": 0,
    "community_cards": ['2h', '5d', '9s'], # Empty [] during pre-flop
    "current_stage": "flop", # "pre-flop", "flop", "turn", "river"
    "pots": [
        # The first pot will always be the main pot. Other pots following it are side pots
        {
            "amount": 100,                  # Total chips in this pot
            "eligible_players": [0,1,2]     # Player IDs who can win this pot
        },
        {
            "amount": 50,
            "eligible_players": [0,2]
        }
    ],

    # --- YOUR STATUS ---
    "your_status": {
        "position": 0,  # Play order THIS hand. Dealer is always at 0
        "player_id": 0,
        "stack": 900,
        "hand_status": "active",        # "active", "folded", "all-in"
        "current_bet_this_stage": 20,   # How much you put in this stage
        "total_bet_this_hand": 50,      # How much you put in this hand
        "can_raise": True               # Whether you can make a raise
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
    # Your status is also included in all player status
    "players": [
        {
            "position": 0,
            "player_id": 0,
            "stack": 900,
            "hand_status": "active",
            "current_bet_this_stage": 20,
            "total_bet_this_hand": 50,
            "can_raise": True
        },
        # ... other players
    ],

    # --- ACTION HISTORY (Crucial for detecting logic) ---
    # A list of sequential actions in the current stage
    # Actions include "ante", "big-blind-ante", "small-blind", "big-blind", "bet", "check", "fold", "call", "raise", "all-in"
    # Stages include "ante", "pre-flop", "flop", "turn", "river"
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
    "community_cards": ['2h', '5d', '9s', 'As', 'Ks'],
    "end_at": "showdown",
    "your_result": {
        "player_id": 0,
        "hand_status": "active",
        "hole_cards": ['Ah', 'Kh'],
        "score": 123123123, # Score evaluated by treys. Lower score means better hand
        "total_bet_this_hand": 1200, # Chips spent
        "winnings": 3600, # Chips gained
        "stack": 2200, # Stack after this hand
        "rank": None # When a player is still in the game, their rank is None
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
            "rank": None # When a player is still in the game, their rank is None
        },
        {
            "player_id": 1,
            "hand_status": "all-in",
            "hole_cards": ['2c', '7d'],
            "score": 123123123,
            "total_bet_this_hand": 1200,
            "winnings": 0,
            "stack": 0, # Player is eliminated when stack is reduced to 0
            "rank": 3 # When a player finishes the game, they will be assigned a rank.
        },
        {
            "player_id": 2,
            "hand_status": "active",
            "hole_cards": None, # Folded earlier, cards remain a mystery
            "score": None, # Folded earlier, score remain a mystery
            "total_committed": 1200,
            "winnings": 0,
            "stack": 500,
            "rank": None
        }, 
    ],
    "hand_log": [...] # Complete list of every bet/check this hand
}
```

Helper function:
```python
def get_positions(player_count: int):
    """Yields indexes of Dealer, Small Blind, Big Blind and Under the Gun."""

    if player_count == 2:
        yield 0     # Dealer
        yield 0     # Small Blind
        yield 1     # Big Blind
        yield 0     # Under the Gun
        return

    yield 0                     # Dealer
    yield 1                     # Small Blind
    yield 2                     # Big Blind
    yield 3 % player_count      # Under the Gun
```