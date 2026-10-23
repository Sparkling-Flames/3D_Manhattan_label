"""Compare the small exact-team smoke output with saved native reference scalars."""
from pathlib import Path
import json
import pandas as pd

HERE = Path(__file__).resolve().parent


def main():
    folder = HERE / "smoke"
    expected = pd.read_csv(folder / "SAVED_EXPECTED_SCALARS.csv")
    actual = pd.read_csv(folder / "native_run/ENDPOINT_SCALARS.csv.gz")
    joined = expected.merge(actual, on="team_key", suffixes=("_saved", "_native"), validate="one_to_one")
    if len(joined) != len(expected):
        raise ValueError("Missing smoke endpoint")
    rows = []
    for field in expected.columns[1:]:
        difference = joined[field + "_native"] - joined[field + "_saved"]
        rows.append(dict(field=field, n=len(joined), max_abs_difference=float(difference.abs().max()),
                         mean_abs_difference=float(difference.abs().mean())))
    table = pd.DataFrame(rows)
    table.to_csv(folder / "SMOKE_COMPATIBILITY.csv", index=False)
    receipt = dict(teams=len(joined), metrics=len(rows),
        all_compatible=bool((table.max_abs_difference < 1e-9).all()),
        max_abs_difference=float(table.max_abs_difference.max()), scalars_columns=list(actual),
        per_endpoint_seconds=actual.native_evaluation_wall_seconds.describe().to_dict(),
        fusion_seconds=actual.fusion_seconds.describe().to_dict(),
        score_seconds=actual.score_seconds.describe().to_dict(),
        identity="existing saved exact teams and new native recomputation; not missing large-block restoration")
    (folder / "SMOKE_COMPATIBILITY_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(table.to_string(index=False))
    if not receipt["all_compatible"]:
        raise ValueError("Native smoke differs from saved reference")


if __name__ == "__main__":
    main()
