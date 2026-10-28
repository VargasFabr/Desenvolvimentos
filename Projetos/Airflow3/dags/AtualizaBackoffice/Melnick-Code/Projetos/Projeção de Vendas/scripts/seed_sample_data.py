import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed sample data for Projecao de Vendas")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing data files if they exist",
    )
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(base_dir)
    data_dir = os.path.join(project_dir, "data")
    sample_files = {
        "empreendimentos": "sample_empreendimentos.json",
        "projecoes": "sample_projecoes.json",
        "series": "sample_projecoes_series.json",
    }
    target_files = {
        "empreendimentos": "empreendimentos.json",
        "projecoes": "projecoes.json",
        "series": "projecoes_series.json",
    }

    for key, sample_name in sample_files.items():
        sample_path = os.path.join(data_dir, sample_name)
        target_path = os.path.join(data_dir, target_files[key])

        if not os.path.exists(sample_path):
            print(f"Sample file not found: {sample_path}")
            return 1

        if os.path.exists(target_path) and not args.force:
            print("Target data already exists. Use --force to overwrite.")
            return 2

        os.makedirs(data_dir, exist_ok=True)
        with open(sample_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        with open(target_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)

        print(f"Seeded sample data to: {target_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
