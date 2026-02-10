from player import Player
from game import PokerGame
from agents.input_agent import InputAgent
from treys import Card, Evaluator


if __name__ == '__main__':
    game_seed = None
    player_list = []
    for i in range(8):
        player_list.append(Player(i, InputAgent(name=f"Input Agent {i}")))
    players = set(player_list)

    game = PokerGame(0, players, 1000, game_seed)

    print(game.game_seed)
    for player in game.player_list:
        print(player.player_id, player.agent.seed)

    first_draw = game.deck.draw(5)
    print(first_draw)
    Card.print_pretty_cards(first_draw)

    game.deck.shuffle()
    second_draw = game.deck.draw(5)
    print(second_draw)
    Card.print_pretty_cards(second_draw)

    evaluator = Evaluator()
    found = False
    hand_count = 0
    while not found:
        hand_count += 1
        game.deck.shuffle()
        public_cards = game.deck.draw(5)
        hole_cards = game.deck.draw(2)
        hand_ranking = evaluator.evaluate(hole_cards, public_cards)
        if hand_ranking <= 1:
            print(f"Found Royal Flush at hand {hand_count}!")
            Card.print_pretty_cards(public_cards)
            Card.print_pretty_cards(hole_cards)
            found = True
