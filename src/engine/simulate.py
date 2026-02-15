from player import Player
from game import PokerGame
from agents.input_agent import InputAgent
from escalator import NoLimitHoldemEscalator
from treys import Card, Evaluator


if __name__ == '__main__':
    game_seed = None
    player_names = {
        0: "Doc. Abrams",
        1: "Senior Junior",
        2: "Jimbo",
        3: "Pluto"
    }
    player_list = []
    for i in range(4):
        player_list.append(Player(i, InputAgent(player_names=player_names), name=player_names[i]))
    players = set(player_list)
    escalator = NoLimitHoldemEscalator()

    game = PokerGame(0, players, escalator, 200, game_seed)
    print(game.game_seed)
    game.run_game()


