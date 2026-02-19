from player import Player
from game import PokerGame
from agents.input_agent import InputAgent
from agents.chatgpt_agent import ChatgptAgent
from agents.gemini_agent import GeminiAgent
from agents.allin_agent import AllInAgent
from agents.claude_agent import ClaudeAgent
from escalator import NoLimitHoldemEscalator
from treys import Card, Evaluator
import csv
from pathlib import Path


if __name__ == '__main__':
    game_seed = None
    player_names = {
        0: "Doc. Abrams",
        1: "Senior Junior",
        2: "Jimbo",
        3: "Pluto",
        4: "River Rat",
        5: "To the Moon",
        6: "Pocket Rockets",
        7: "Robin",
        8: "Opaque City",
        9: "StackOverFlow",
        10: "The Fool"
    }

    results = []

    for game_id in range(1000):
        player_list = []

        i = 0
        for _ in range(1):
            player = Player(i, ChatgptAgent(), player_names[i])
            player_list.append(player)
            i += 1
        for _ in range(1):
            player = Player(i, GeminiAgent(), player_names[i])
            player_list.append(player)
            i += 1
        for _ in range(1):
            player = Player(i, ClaudeAgent(), player_names[i])
            player_list.append(player)
            i += 1
        for _ in range(1):
            player = Player(i, AllInAgent(), player_names[i])
            player_list.append(player)
            i += 1

        # player = Player(10, InputAgent(player_names=player_names), player_names[10])
        # player_list.append(player)

        players = set(player_list)
        escalator = NoLimitHoldemEscalator()

        game = PokerGame(game_id, players, escalator, 3000, game_seed)
        print(f"Seed for Game {game_id} is: {game.game_seed}")
        game.run_game()
        # game.print_ranks()
        for result in game.get_results():
            results.append(result)

    # for result in results:
    #     print(result)

    path = Path("../data/results.csv")

    # Create directory if it doesn't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Now open the file (it will be created automatically if missing)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["game_id", "game_seed", "agent_name", "rank", "hand_count"])
        writer.writeheader()
        writer.writerows(results)

