# csv_updater.py
"""Pandas-based CSV updater for Twist_Deg values."""
import pandas as pd


class CSVUpdater:
    """Loads CSV once, applies batch updates, saves once at end."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.df = pd.read_csv(csv_path)

    def update_twist(self, pile_number: int, new_twist: float) -> bool:
        """Update Twist_Deg for the given UPN. Returns True if UPN found."""
        mask = self.df["UPN"] == pile_number
        if not mask.any():
            return False
        self.df.loc[mask, "Twist_Deg"] = round(new_twist, 2)
        return True

    def save(self):
        """Write the updated DataFrame back to CSV."""
        self.df.to_csv(self.csv_path, index=False)
