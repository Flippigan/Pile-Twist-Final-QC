# tests/test_csv_updater.py
import pandas as pd
import pytest
from csv_updater import CSVUpdater


class TestCSVUpdater:
    def test_update_existing_upn(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        assert updater.update_twist(2787, -0.89) is True
        updater.save()
        df = pd.read_csv(sample_csv)
        assert df.loc[df["UPN"] == 2787, "Twist_Deg"].values[0] == -0.89

    def test_nonexistent_upn_returns_false(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        assert updater.update_twist(11111, 1.0) is False

    def test_multiple_updates_single_save(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        updater.update_twist(2787, -0.89)
        updater.update_twist(777, 2.65)
        updater.save()
        df = pd.read_csv(sample_csv)
        assert df.loc[df["UPN"] == 2787, "Twist_Deg"].values[0] == -0.89
        assert df.loc[df["UPN"] == 777, "Twist_Deg"].values[0] == 2.65

    def test_overwrites_existing_twist_value(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        updater.update_twist(2787, 1.0)
        updater.update_twist(2787, -0.89)  # overwrite
        updater.save()
        df = pd.read_csv(sample_csv)
        assert df.loc[df["UPN"] == 2787, "Twist_Deg"].values[0] == -0.89

    def test_preserves_other_columns(self, sample_csv):
        updater = CSVUpdater(str(sample_csv))
        updater.update_twist(2787, -0.89)
        updater.save()
        df = pd.read_csv(sample_csv)
        row = df[df["UPN"] == 2787].iloc[0]
        assert row["Detected"] == False  # pandas reads "FALSE" as bool
        assert row["Pile_Height"] == 0
