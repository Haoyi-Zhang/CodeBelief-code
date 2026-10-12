#!/usr/bin/env python3
"""Render retained constructive checks as vector figures; no experiments run."""
from pathlib import Path
import argparse
import csv
import shutil
from fractions import Fraction
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt, font_manager
from matplotlib.ticker import NullLocator

ROOT = Path(__file__).resolve().parents[1]


def configure_fonts():
    files = [ROOT / "fonts" / name for name in
             ("LinLibertine_Rah.ttf", "LinLibertine_RIah.ttf")]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(f"Packaged Libertine font missing: {path}")
        font_manager.fontManager.addfont(str(path))
    family = font_manager.FontProperties(fname=str(files[0])).get_name()
    plt.rcParams.update({"font.family": family, "font.size": 8.468,
                         "mathtext.fontset": "custom", "mathtext.rm": family,
                         "mathtext.it": family + ":style=italic",
                         "mathtext.bf": family, "mathtext.fallback": None,
                         "text.usetex": False, "pdf.fonttype": 42,
                         "ps.fonttype": 42, "pdf.use14corefonts": False,
                         "axes.linewidth": .4, "axes.labelsize": 7.97,
                         "axes.titlesize": 7.97, "xtick.major.size": 2.1,
                         "ytick.major.size": 2.1, "xtick.major.width": .4,
                         "ytick.major.width": .4, "axes.unicode_minus": True})
    print("Font:", family)


def read(name):
    with (ROOT / "results" / name).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def style(ax):
    ax.xaxis.labelpad = 1
    ax.set_axisbelow(True)
    ax.grid(True, which="major", color=".86", linewidth=.3)
    ax.tick_params(direction="in", top=True, right=True, pad=3)
    ax.xaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_minor_locator(NullLocator())


def figures():
    theory = read("joint-theory.csv")
    fig = plt.figure(figsize=(372.3023 / 72, 136.0791 / 72))
    for index, (family, title, color, marker, limits, ticks) in enumerate([
        ("two-approx-tight", "(a) Independent sides", "#00008c", "o", (1, 2.08), [1, 1.5, 2]),
        ("deletion-gap", "(b) Adverse deletion", ".35", "s", (-2, 132), [1, 32, 64, 128]),
    ]):
        ax = fig.add_axes([(33.05 if index == 0 else 222.14) / 372.3023,
                           20.20 / 136.0791, 144.26 / 372.3023, 96.90 / 136.0791])
        rows = [r for r in theory if r["family"] == family]
        x = [int(r["parameter"]) for r in rows]
        y = [float(Fraction(int(r["baseline"]), int(r["optimum"]))) for r in rows]
        if family == "two-approx-tight":
            assert all(Fraction(int(r["baseline"]), int(r["optimum"])) ==
                       Fraction(2 * int(r["parameter"]), int(r["parameter"]) + 1)
                       for r in rows)
        else:
            assert all(v == n for n, v in zip(x, y))
        ax.set_xscale("log", base=2)
        ax.plot(x, y, color=color, linewidth=.6, marker=marker, markersize=3.8)
        ax.set(xlim=(1.8, 145), ylim=limits, xlabel="family parameter",
               ylabel="baseline / optimum", title=title)
        ax.set_xticks([2, 8, 32, 128], ["2", "8", "32", "128"])
        ax.set_yticks(ticks, [str(t) for t in ticks])
        ax.title.set_position((.5, 1.10))
        style(ax)
    yield "ratio-plot", fig

    rows = read("joint-scaling.csv")
    x = [int(r["alternatives_per_side"]) for r in rows]
    y = [int(r["candidate_pairs"]) for r in rows]
    assert all(p == n * n for n, p in zip(x, y))
    fig = plt.figure(figsize=(412.9433 / 72, 118.6797 / 72))
    ax = fig.add_axes([29.8 / 412.9433, 21.78 / 118.6797,
                       382.4 / 412.9433, 96.30 / 118.6797])
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=2)
    ax.plot(x, y, color="blue", linewidth=.6, marker="o", markersize=3.8)
    ax.set(xlim=(2**.3, 2**8.7), ylim=(2**.6, 2**17.4),
           xlabel="minimal alternatives per side", ylabel="candidate support pairs")
    ax.set_xticks(x, [rf"$2^{{{i}}}$" for i in range(1, 9)])
    ax.set_yticks(y, [rf"$2^{{{i}}}$" for i in range(2, 17, 2)])
    style(ax)
    yield "frontier-plot", fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "figures")
    parser.add_argument("--paper-dir", type=Path, default=ROOT.parent / "paper" / "figures")
    args = parser.parse_args()
    configure_fonts()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, fig in figures():
        path = args.out / (name + ".pdf")
        fig.savefig(path, metadata={"Creator": None, "Producer": None,
                                    "CreationDate": None, "ModDate": None})
        plt.close(fig)
        if args.paper_dir.is_dir():
            shutil.copyfile(path, args.paper_dir / path.name)
        print("Rendered", name)


if __name__ == "__main__":
    main()
