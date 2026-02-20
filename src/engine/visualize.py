import pandas as pd
import matplotlib.pyplot as plt

SAVE_PATH = "../../data"

def load_data(path):
    return pd.read_csv(path)

def add_normalized_rank(df):
    df["normalized_rank"] = 1 - (df["rank"] - 1) / (
        df.groupby("game_id")["rank"].transform("max") - 1
    )
    return df

def plot_rank_distribution(df):
    agents = df["agent_name"].unique()

    for agent in agents:
        agent_df = df[df["agent_name"] == agent]

        # Count occurrences of each rank (1–8)
        rank_counts = (
            agent_df["rank"]
            .value_counts()
            .reindex(range(1, 9), fill_value=0)
            .sort_index()
        )

        plt.figure()

        plt.bar(
            rank_counts.index,
            rank_counts.values,
            width=0.5  # smaller width = visible gaps
        )

        plt.xlim(0.5, 4.5)
        plt.xticks(range(1, 5))

        plt.ylim(0, 600)

        plt.xlabel("Rank")
        plt.ylabel("Frequency")
        plt.title(f"Rank Distribution - {agent}")
        plt.savefig(f"{SAVE_PATH}/rank_distribution_{agent}.png")
        plt.close()

def plot_hand_count_distribution(df):
    agents = df["agent_name"].unique()

    for agent in agents:
        agent_df = df[df["agent_name"] == agent]

        plt.figure()
        plt.hist(agent_df["hand_count"], bins=30)

        plt.xlim(0, 150)

        plt.ylim(0, 100)

        plt.title(f"Hand Count Distribution - {agent}")
        plt.xlabel("Hand Count")
        plt.ylabel("Frequency")
        plt.savefig(f"{SAVE_PATH}/hand_count_{agent}.png")
        plt.close()

def plot_win_counts(df):
    win_counts = (
        df[df["rank"] == 1]
        .groupby("agent_name")
        .size()
    )

    plt.figure()
    win_counts.sort_values(ascending=False).plot(kind="bar")
    plt.title("Number of Wins by Agent")
    plt.ylabel("Wins")
    plt.xlabel("Agent")
    plt.xticks(rotation=0)
    plt.savefig(f"{SAVE_PATH}/win_counts.png")
    plt.close()

def main():
    df = load_data("../../data/results.csv")
    # df = add_normalized_rank(df)

    plot_rank_distribution(df)
    plot_hand_count_distribution(df)
    plot_win_counts(df)

if __name__ == "__main__":
    main()