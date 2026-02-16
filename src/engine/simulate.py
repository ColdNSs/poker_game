from player import Player
from game import PokerGame
from agents.input_agent import InputAgent
from agents.chatgpt_agent import ChatgptAgent
from agents.gemini_agent import GeminiAgent
from agents.allin_agent import AllInAgent
from escalator import NoLimitHoldemEscalator
from treys import Card, Evaluator


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
    player_list = []

    i = 0
    for _ in range(4):
        player = Player(i, ChatgptAgent(), player_names[i])
        player_list.append(player)
        i += 1
    for _ in range(4):
        player = Player(i, GeminiAgent(), player_names[i])
        player_list.append(player)
        i += 1
    for _ in range(0):
        player = Player(i, AllInAgent(), player_names[i])
        player_list.append(player)
        i += 1

    # player = Player(10, InputAgent(player_names=player_names), player_names[10])
    # player_list.append(player)

    players = set(player_list)
    escalator = NoLimitHoldemEscalator()

    game = PokerGame(0, players, escalator, 2000, game_seed)
    print(game.game_seed)
    game.run_game()


