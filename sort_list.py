import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# Locate the data folder next to this script.
project_folder = Path(__file__).resolve().parent
data_folder = project_folder / "data"
list_file = data_folder / "_list.json"

API_URL = "https://api.aredl.net/v2/api/aredl/levels/"


def main():
    # --auto lets GitHub Actions save without asking for input.
    automatic = "--auto" in sys.argv

    # 1. Read your current list.
    with list_file.open(encoding="utf-8") as file:
        levels = json.load(file)

    if not isinstance(levels, list) or not all(
        isinstance(name, str) for name in levels
    ):
        raise ValueError("_list.json must contain a list of filenames.")

    if len(levels) != len(set(levels)):
        raise ValueError("_list.json contains duplicate filenames.")

    # 2. Download AREDL rankings.
    print("Downloading AREDL rankings...")

    request = Request(
        API_URL,
        headers={
            "User-Agent": "BesterRegen-Demonlist/1.0",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        aredl_levels = json.load(response)

    if not isinstance(aredl_levels, list) or not aredl_levels:
        raise ValueError("AREDL returned an empty or unexpected response.")

    # 3. Match GD level IDs to AREDL ranks.
    positions = {}

    for level in aredl_levels:
        level_id = level["level_id"]
        position = level["position"]

        if type(level_id) is not int or type(position) is not int:
            raise ValueError("AREDL returned an invalid ID or rank.")

        if position < 1:
            raise ValueError("AREDL returned an invalid rank.")

        positions[level_id] = position

    print(f"Received {len(positions)} levels from AREDL.")

    # 4. Find the rank of each level on your server.
    list_positions = {}
    missing_levels = []

    for name in levels:
        level_file = data_folder / f"{name}.json"

        with level_file.open(encoding="utf-8") as file:
            details = json.load(file)

        level_id = details["id"]

        if level_id in positions:
            list_positions[name] = positions[level_id]
        else:
            missing_levels.append((name, level_id))

    # Stop rather than saving a list with missing levels.
    if missing_levels:
        print("\nThese levels were not found on AREDL:")

        for name, level_id in missing_levels:
            print(f"  - {name} (GD ID: {level_id})")

        raise ValueError(
            "No files changed. Check these IDs or decide how "
            "unranked levels should be placed."
        )

    # 5. Sort your filenames by AREDL rank.
    def get_rank(name):
        return list_positions[name]

    sorted_levels = sorted(levels, key=get_rank)

    # 6. Preview the sorted list.
    print("\nSorted server list:\n")

    for server_rank, name in enumerate(sorted_levels, start=1):
        aredl_rank = list_positions[name]
        print(f"{server_rank:>3}. {name} — AREDL #{aredl_rank}")

    if sorted_levels == levels:
        print("\nYour list is already in this order. No files changed.")
        return

    # 7. Ask before saving unless running with --auto.
    if not automatic:
        answer = input("\nSave this order to data/_list.json? [y/N]: ")

        if answer.strip().lower() != "y":
            print("No files changed.")
            return

    # 8. Make a backup when running interactively on your PC.
    # Automated changes are tracked by the workflow's Git commit.
    if not automatic:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_file = data_folder / f"_list.backup-{timestamp}.json"

        shutil.copy2(list_file, backup_file)
        print(f"\nBackup created: {backup_file.name}")

    # 9. Write a temporary file, then replace the original.
    temporary_file = data_folder / "_list.json.tmp"

    try:
        with temporary_file.open("w", encoding="utf-8") as file:
            json.dump(sorted_levels, file, indent=4, ensure_ascii=False)
            file.write("\n")

        temporary_file.replace(list_file)
    finally:
        if temporary_file.exists():
            temporary_file.unlink()

    print("\nSaved the new order to data/_list.json.")

    if automatic:
        print("The GitHub workflow can now commit this change.")
    else:
        print("Upload or commit the updated file to GitHub.")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        print(f"\nAREDL refused the request: HTTP {error.code}.")
        sys.exit(1)
    except URLError as error:
        print(f"\nCould not connect to AREDL: {error.reason}")
        sys.exit(1)
    except TimeoutError:
        print("\nThe AREDL request timed out. Try again later.")
        sys.exit(1)
    except json.JSONDecodeError as error:
        print(f"\nCould not read JSON: {error}")
        sys.exit(1)
    except (KeyError, TypeError, ValueError) as error:
        print(f"\nUnexpected or missing data: {error}")
        sys.exit(1)
    except OSError as error:
        print(f"\nFile or network error: {error}")
        sys.exit(1)