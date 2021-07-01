import subprocess
import pathlib
from sys import executable

# install all required packages


def install():
    root = pathlib.Path(__file__).parent
    main_req = root.joinpath("requirements.txt")

    sets = set()

    def requirement_gen():
        modules = main_req.read_text().split()
        print(f"In [{main_req}]:\n{' '.join(modules)}\n")
        sets.update(modules)

        for path_ in root.joinpath("Meowpy/BotComponents").iterdir():
            if not path_.is_dir():
                continue

            req_file = path_.joinpath("requirements.txt")

            if req_file.exists():
                component_modules = req_file.read_text().split()
                print(f"In [{req_file}]:\n{' '.join(component_modules)}\n")
                sets.update(component_modules)

        return sets

    lists = tuple(requirement_gen())

    input_ = input("Install these modules? (y/n): ")

    if input_ not in "yY":
        print("Installation canceled.")
        return

    for idx, req in enumerate(lists, 1):
        print(f"\n[{idx}/{len(lists)}] Installing {req}")
        subprocess.check_call([executable, "-m", "pip", "install", req])


if __name__ == '__main__':
    install()
