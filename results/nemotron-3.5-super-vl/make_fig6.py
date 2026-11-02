#!/usr/bin/env python3
"""Draw fig6_ssh.png from trials.csv (T1/T5 rows with shell-call counts).
Usage: python3 make_fig6.py trials.csv fig6_ssh.png
Needs matplotlib only (pip install matplotlib). No fonts required (labels are English).
"""
import csv, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
INK="#0b0b0b"; INK2="#52514e"; GRID="#e4e3df"; BLUE="#2a78d6"; ORANGE="#eb6834"
src, dst = sys.argv[1], sys.argv[2]
P=[]
for r in csv.DictReader(open(src)):
    if r["shell_calls"]:
        P.append((r["reasoning"], r["task"], int(r["shell_calls"]), int(r["shell_calls_via_ssh"]), int(r["score"])))
fig,ax=plt.subplots(figsize=(9,6),dpi=150)
ax.axvspan(0,26,color="#fbe9e1",zorder=0)
ax.text(1.5,44,"Runs that dropped ssh after\nthe first two calls and\ninspected their own container",ha="left",va="top",color="#a2401a",fontsize=10,zorder=4)
for th,t,sh,ss,sc in P:
    ax.plot(ss/sh*100,sc,marker="o" if t=="T1" else "s",color=BLUE if th=="medium" else ORANGE,ms=10,mec="white",mew=1.3,ls="none",zorder=3)
ax.set_xlim(0,102); ax.set_ylim(-2,46)
ax.set_xlabel("Share of shell calls made through ssh to the target servers (%)",color=INK)
ax.set_ylabel("Score (/45)",color=INK)
for s in ["top","right"]: ax.spines[s].set_visible(False)
for s in ["left","bottom"]: ax.spines[s].set_color(INK2)
ax.tick_params(colors=INK2); ax.grid(color=GRID,linewidth=0.8); ax.set_axisbelow(True)
ax.set_title("Nemotron 3.5 Super VL: score vs. ssh usage (T1 and T5, 3 runs each)",color=INK,fontsize=13,loc="left")
ax.legend(handles=[Line2D([0],[0],color=BLUE,marker="o",ms=9,mec="white",ls="none",label="medium reasoning, T1 survey"),
                   Line2D([0],[0],color=BLUE,marker="s",ms=9,mec="white",ls="none",label="medium reasoning, T5 config fixes"),
                   Line2D([0],[0],color=ORANGE,marker="o",ms=9,mec="white",ls="none",label="full reasoning, T1 survey"),
                   Line2D([0],[0],color=ORANGE,marker="s",ms=9,mec="white",ls="none",label="full reasoning, T5 config fixes")],
          loc="upper center",bbox_to_anchor=(0.5,-0.12),ncol=2,frameon=False,fontsize=9.5)
fig.tight_layout(); fig.savefig(dst,facecolor="white")
print("wrote", dst, len(P), "points")
