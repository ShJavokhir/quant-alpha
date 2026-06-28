"""Convert the web research corpus into validated DSL alphas (cached)."""
from lab import config
from lab.agent.researcher import Researcher


def main():
    panel = config.load_panel("base")
    r = Researcher()
    r.build_cache(panel=panel, verbose=True)
    valid = [e for e in r.cache.values() if e.get("formula") and e.get("valid")]
    print(f"DONE converted {len(r.cache)} ideas; {len(valid)} valid & backtest-able", flush=True)


if __name__ == "__main__":
    main()
