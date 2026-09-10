# 反転（key=reversal）の検討記録

角度は短期の反転です。大きく動いた後の戻りを買う、または売る。3日リターンの z スコア、RSI の極端、ボラ急騰の3つを見ました。
物差しは harness.py だけです。期間は train（2022-09〜2025-03）で探し、valid（2025-03〜2026-03）は最後に1回だけ見ました。test は見ていません。
コストは DEFAULT_COSTS（テイカー0.12%＋すべり0.05%を片道、ショートに建玉管理料0.04%/日）、position=0.10 です。
スクリプトと生の出力は `explore_reversal/` にあります（diag1.py, stage1.py, s2_*.py, s3_*.py, s4_valid.py, s5_valid_episodes.py と同名の .out）。

## 結論を先に

- **対称な反転は無い。** 買われすぎ側（RSI>70、z>+1.5）は train で反転せず続伸します。買われすぎを売る対称版は1回あたり -1.5% です。
- **3日リターンの z スコアで測った反転も無い。** z72<-1.5 と z72<-2 で買うと、5銘柄とも1回あたり -0.5〜-1.5% です。3日下げた後はもう少し下げます。
- **あるのは、極端な売られすぎの戻りだけです。** RSI(24)<20 で買って72時間持つと、train で1回あたり +3.83%（n=40、t=3.17）、valid で +5.37%（n=15、t=2.34）です。
- ただし件数が少なすぎます。train の40件は20回の出来事、valid の15件は9回の出来事です。出来事の単位で数えると valid の t は 1.36 です。btc と eth だけなら valid は n=6、平均 +0.63%、t 0.23 で、何も言えません。
- 同じ頻度でランダムに買うだけの戦略を300個 train で回すと、t≧3.17 が7個、平均≧3.83% が11個出ます。52個の変種を試した後の t=3.17 は、運と切り分けられていません。

## 1. 診断（train のみ、コスト前、close-to-close）

`diag1.py`。条件付けた H 時間先のリターンの平均を出しました。件数は毎時の重なりありなので、独立な出来事はずっと少ないです。

要点だけ書きます（pooled は5銘柄）。
- 過去24hの z が +1.5 以上だと、H=72 で +1.25〜+3.56%。続伸です。-3 未満だけ +1.44%、[-3,-2) は -0.80%。
- 過去72hの z（3日リターン）。[-3,-2) は -0.83%、[-2,-1.5) は -0.52%、-3 未満は +2.29%（n=433、出来事はごく少数）。
- 過去168hの z。負の側は全部プラス（-2 未満 +1.73%、[-2,-1.5) +0.86%、[-1.5,-1) +1.20%、H=72）。ただし中立 [-1,1) も +0.15% あって、bull の drift が乗っています。
- RSI(14)。<20 で +1.32%、[25,35) は -0.15〜-0.80%、>70 は +1.4〜+1.8%（続伸）。
- RSI(24)。<20 で +3.15%、[20,25) +1.87%、[25,35) は -0.9%、>65 は +1.4〜+2.1%（続伸）。
- RSI(48)。<30 で +3.8〜+4.1%、[30,35) -1.23%、>65 続伸。
- ボラ急騰（24h sd / 240h sd）× 直近24hの向き。符号が銘柄ごとにばらばらで、反転の形は無し。この族は落としました。

## 2. stage 1: 変種 47 個（train、H ごと、fill=next_open、hold_through=False）

`stage1.py` の出力をそのまま貼ります。pooled は5銘柄です。

```
rsi14<20 H24                 pooled n= 189 mean=+0.447 sd=5.24 t=+1.17 hit=49.7 | btc_ n= 39 m=-0.40 t=-0.69 | eth_ n= 41 m=-0.58 t=-1.08 | xrp_ n= 33 m=+2.49 t=+1.71 | ltc_ n= 40 m=+0.47 t=+0.68 | doge n= 36 m=+0.64 t=+0.72
rsi14<20 H48                 pooled n= 179 mean=+0.493 sd=6.57 t=+1.00 hit=55.3 | btc_ n= 37 m=-0.29 t=-0.45 | eth_ n= 39 m=-1.16 t=-1.79 | xrp_ n= 31 m=+2.78 t=+1.26 | ltc_ n= 37 m=+1.22 t=+1.46 | doge n= 35 m=+0.37 t=+0.49
rsi14<20 H72                 pooled n= 174 mean=+0.932 sd=7.37 t=+1.67 hit=54.6 | btc_ n= 37 m=-0.02 t=-0.02 | eth_ n= 38 m=-1.19 t=-1.44 | xrp_ n= 30 m=+3.09 t=+1.36 | ltc_ n= 36 m=+2.36 t=+2.10 | doge n= 33 m=+0.91 t=+0.86
rsi14<25 H24                 pooled n= 412 mean=-0.215 sd=4.32 t=-1.01 hit=50.5 | btc_ n= 90 m=-0.29 t=-0.90 | eth_ n= 84 m=-0.58 t=-1.37 | xrp_ n= 84 m=+0.39 t=+0.70 | ltc_ n= 76 m=-0.00 t=-0.01 | doge n= 78 m=-0.59 t=-1.10
rsi14<25 H48                 pooled n= 360 mean=-0.375 sd=6.45 t=-1.10 hit=47.8 | btc_ n= 80 m=-0.35 t=-0.78 | eth_ n= 73 m=-1.15 t=-1.93 | xrp_ n= 74 m=+1.55 t=+1.43 | ltc_ n= 68 m=-0.47 t=-0.63 | doge n= 65 m=-1.63 t=-2.09
rsi14<25 H72                 pooled n= 330 mean=-0.308 sd=7.44 t=-0.75 hit=47.9 | btc_ n= 72 m=-0.47 t=-0.88 | eth_ n= 67 m=-1.59 t=-2.03 | xrp_ n= 68 m=+1.57 t=+1.26 | ltc_ n= 63 m=+0.61 t=+0.77 | doge n= 60 m=-1.77 t=-1.68
rsi14<30 H24                 pooled n= 796 mean=-0.285 sd=3.96 t=-2.03 hit=50.8 | btc_ n=173 m=-0.37 t=-1.80 | eth_ n=167 m=-0.22 t=-0.75 | xrp_ n=154 m=-0.20 t=-0.55 | ltc_ n=146 m=-0.46 t=-1.41 | doge n=156 m=-0.17 t=-0.46
rsi14<30 H48                 pooled n= 658 mean=-0.113 sd=5.71 t=-0.51 hit=50.6 | btc_ n=144 m=-0.18 t=-0.60 | eth_ n=138 m=-0.05 t=-0.11 | xrp_ n=129 m=+0.56 t=+0.83 | ltc_ n=118 m=-0.80 t=-1.61 | doge n=129 m=-0.16 t=-0.29
rsi14<30 H72                 pooled n= 567 mean=+0.048 sd=7.07 t=+0.16 hit=50.3 | btc_ n=118 m=-0.51 t=-1.24 | eth_ n=124 m=+0.21 t=+0.35 | xrp_ n=113 m=+1.04 t=+1.28 | ltc_ n=104 m=-0.26 t=-0.40 | doge n=108 m=-0.27 t=-0.34
rsi24<20 H24                 pooled n=  42 mean=+2.555 sd=5.65 t=+2.93 hit=66.7 | btc_ n=  7 m=+0.67 t=+0.39 | eth_ n= 10 m=+1.55 t=+1.00 | xrp_ n=  8 m=+3.90 t=+1.69 | ltc_ n=  7 m=+1.85 t=+0.72 | doge n= 10 m=+4.30 t=+2.30
rsi24<20 H48                 pooled n=  40 mean=+3.159 sd=6.27 t=+3.19 hit=70.0 | btc_ n=  6 m=+1.84 t=+0.83 | eth_ n= 10 m=+1.34 t=+1.18 | xrp_ n=  7 m=+3.18 t=+0.99 | ltc_ n=  7 m=+3.23 t=+1.12 | doge n= 10 m=+5.70 t=+2.82
rsi24<20 H72                 pooled n=  40 mean=+3.827 sd=7.64 t=+3.17 hit=75.0 | btc_ n=  6 m=+2.59 t=+1.19 | eth_ n= 10 m=+2.40 t=+1.42 | xrp_ n=  7 m=+5.22 t=+0.95 | ltc_ n=  7 m=+4.24 t=+1.94 | doge n= 10 m=+4.73 t=+2.38
rsi24<25 H24                 pooled n= 114 mean=+0.767 sd=5.94 t=+1.38 hit=51.8 | btc_ n= 23 m=-0.29 t=-0.39 | eth_ n= 26 m=-0.50 t=-0.57 | xrp_ n= 21 m=+2.05 t=+1.20 | ltc_ n= 24 m=+0.85 t=+0.92 | doge n= 20 m=+2.19 t=+1.16
rsi24<25 H48                 pooled n= 108 mean=+0.331 sd=5.46 t=+0.63 hit=54.6 | btc_ n= 21 m=+0.23 t=+0.24 | eth_ n= 25 m=-0.56 t=-0.71 | xrp_ n= 20 m=+0.60 t=+0.38 | ltc_ n= 23 m=-0.08 t=-0.06 | doge n= 19 m=+1.82 t=+1.32
rsi24<25 H72                 pooled n= 104 mean=+0.293 sd=7.43 t=+0.40 hit=51.9 | btc_ n= 21 m=-0.21 t=-0.17 | eth_ n= 24 m=-1.19 t=-1.05 | xrp_ n= 19 m=+0.54 t=+0.24 | ltc_ n= 22 m=+1.21 t=+0.61 | doge n= 18 m=+1.48 t=+0.96
rsi24<30 H24                 pooled n= 304 mean=-0.246 sd=5.20 t=-0.83 hit=48.0 | btc_ n= 62 m=-0.43 t=-0.98 | eth_ n= 61 m=-1.08 t=-2.01 | xrp_ n= 58 m=+0.82 t=+0.95 | ltc_ n= 63 m=-0.05 t=-0.07 | doge n= 60 m=-0.45 t=-0.58
rsi24<30 H48                 pooled n= 256 mean=-0.322 sd=7.00 t=-0.74 hit=46.9 | btc_ n= 54 m=-0.63 t=-1.15 | eth_ n= 50 m=-1.60 t=-1.82 | xrp_ n= 50 m=+1.52 t=+1.03 | ltc_ n= 52 m=-0.15 t=-0.17 | doge n= 50 m=-0.73 t=-0.78
rsi24<30 H72                 pooled n= 237 mean=+0.017 sd=7.41 t=+0.04 hit=50.6 | btc_ n= 49 m=-0.19 t=-0.29 | eth_ n= 47 m=-1.98 t=-2.28 | xrp_ n= 48 m=+2.06 t=+1.41 | ltc_ n= 47 m=+0.87 t=+0.77 | doge n= 46 m=-0.72 t=-0.71
rsi48<20 H24                 pooled n=   4 mean=+1.351 sd=5.40 t=+0.50 hit=50.0 | btc_ n=  1 m=-3.51 t=+nan | eth_ n=  2 m=+2.81 t=+0.53 | xrp_ n=  1 m=+3.29 t=+nan | ltc_ n=  0 m=+nan t=+nan | doge n=  0 m=+nan t=+nan
rsi48<20 H48                 pooled n=   4 mean=+2.000 sd=5.62 t=+0.71 hit=50.0 | btc_ n=  1 m=-3.46 t=+nan | eth_ n=  2 m=+3.18 t=+0.62 | xrp_ n=  1 m=+5.09 t=+nan | ltc_ n=  0 m=+nan t=+nan | doge n=  0 m=+nan t=+nan
rsi48<20 H72                 pooled n=   4 mean=+2.366 sd=5.59 t=+0.85 hit=50.0 | btc_ n=  1 m=-3.22 t=+nan | eth_ n=  2 m=+2.00 t=+0.60 | xrp_ n=  1 m=+8.69 t=+nan | ltc_ n=  0 m=+nan t=+nan | doge n=  0 m=+nan t=+nan
rsi48<25 H24                 pooled n=  19 mean=+3.286 sd=7.06 t=+2.03 hit=63.2 | btc_ n=  3 m=-0.18 t=-0.04 | eth_ n=  5 m=+2.27 t=+0.74 | xrp_ n=  3 m=+2.73 t=+0.83 | ltc_ n=  4 m=+3.16 t=+0.72 | doge n=  4 m=+7.70 t=+2.01
rsi48<25 H48                 pooled n=  19 mean=+4.456 sd=7.36 t=+2.64 hit=68.4 | btc_ n=  3 m=+1.50 t=+0.30 | eth_ n=  5 m=+1.28 t=+0.62 | xrp_ n=  3 m=+5.82 t=+1.66 | ltc_ n=  4 m=+5.07 t=+1.09 | doge n=  4 m=+9.01 t=+2.03
rsi48<25 H72                 pooled n=  19 mean=+4.557 sd=6.48 t=+3.06 hit=78.9 | btc_ n=  3 m=+3.07 t=+0.64 | eth_ n=  5 m=+2.64 t=+0.85 | xrp_ n=  3 m=+4.58 t=+1.77 | ltc_ n=  4 m=+6.05 t=+1.88 | doge n=  4 m=+6.55 t=+1.56
rsi48<30 H24                 pooled n=  59 mean=+1.997 sd=7.86 t=+1.95 hit=59.3 | btc_ n=  9 m=-0.74 t=-0.58 | eth_ n= 14 m=+0.53 t=+0.37 | xrp_ n= 13 m=+4.60 t=+1.61 | ltc_ n= 11 m=+0.77 t=+0.43 | doge n= 12 m=+4.08 t=+1.34
rsi48<30 H48                 pooled n=  53 mean=+1.432 sd=6.49 t=+1.61 hit=60.4 | btc_ n=  8 m=-0.79 t=-0.44 | eth_ n= 13 m=+0.60 t=+0.51 | xrp_ n= 11 m=+2.81 t=+1.25 | ltc_ n= 10 m=+0.29 t=+0.12 | doge n= 11 m=+3.70 t=+1.66
rsi48<30 H72                 pooled n=  52 mean=+1.013 sd=7.85 t=+0.93 hit=55.8 | btc_ n=  8 m=-2.16 t=-1.10 | eth_ n= 13 m=-0.42 t=-0.24 | xrp_ n= 11 m=+3.18 t=+0.98 | ltc_ n=  9 m=+0.60 t=+0.21 | doge n= 11 m=+3.19 t=+1.58
z72<-1.5 H24                 pooled n= 425 mean=-0.519 sd=4.83 t=-2.22 hit=46.4 | btc_ n= 80 m=-0.76 t=-1.99 | eth_ n= 95 m=-0.59 t=-1.23 | xrp_ n= 75 m=-0.72 t=-0.99 | ltc_ n= 88 m=-0.41 t=-0.81 | doge n= 87 m=-0.15 t=-0.30
z72<-1.5 H48                 pooled n= 289 mean=-0.590 sd=6.18 t=-1.62 hit=43.6 | btc_ n= 54 m=-0.87 t=-1.29 | eth_ n= 66 m=-0.39 t=-0.55 | xrp_ n= 48 m=-0.94 t=-0.97 | ltc_ n= 60 m=-0.17 t=-0.18 | doge n= 61 m=-0.70 t=-0.90
z72<-1.5 H72                 pooled n= 220 mean=-0.748 sd=7.48 t=-1.48 hit=45.0 | btc_ n= 41 m=-1.40 t=-1.93 | eth_ n= 49 m=-0.93 t=-1.02 | xrp_ n= 37 m=-1.15 t=-0.67 | ltc_ n= 49 m=+0.38 t=+0.31 | doge n= 44 m=-0.85 t=-0.84
z72<-2.0 H24                 pooled n= 200 mean=-0.550 sd=5.40 t=-1.44 hit=50.5 | btc_ n= 40 m=-0.43 t=-0.65 | eth_ n= 50 m=-0.89 t=-1.19 | xrp_ n= 36 m=-0.61 t=-0.62 | ltc_ n= 36 m=-0.28 t=-0.26 | doge n= 38 m=-0.43 t=-0.48
z72<-2.0 H48                 pooled n= 141 mean=-1.026 sd=5.83 t=-2.09 hit=49.6 | btc_ n= 28 m=-0.81 t=-0.85 | eth_ n= 33 m=-2.01 t=-2.44 | xrp_ n= 27 m=-0.46 t=-0.36 | ltc_ n= 26 m=-0.13 t=-0.09 | doge n= 27 m=-1.46 t=-1.59
z72<-2.0 H72                 pooled n= 125 mean=-1.517 sd=7.02 t=-2.41 hit=45.6 | btc_ n= 27 m=-0.96 t=-0.89 | eth_ n= 28 m=-2.29 t=-1.42 | xrp_ n= 22 m=-2.52 t=-1.68 | ltc_ n= 22 m=-0.21 t=-0.13 | doge n= 26 m=-1.52 t=-1.27
z72<-3.0 H24                 pooled n=  40 mean=+2.000 sd=9.04 t=+1.40 hit=55.0 | btc_ n=  9 m=-1.25 t=-1.30 | eth_ n=  8 m=-0.72 t=-0.31 | xrp_ n=  8 m=+4.88 t=+1.11 | ltc_ n=  8 m=-1.24 t=-0.64 | doge n=  7 m=+9.70 t=+2.21
z72<-3.0 H48                 pooled n=  32 mean=+2.322 sd=7.92 t=+1.66 hit=62.5 | btc_ n=  7 m=-1.08 t=-0.75 | eth_ n=  7 m=-0.09 t=-0.04 | xrp_ n=  7 m=+4.69 t=+1.55 | ltc_ n=  5 m=-2.67 t=-0.87 | doge n=  6 m=+10.51 t=+2.99
z72<-3.0 H72                 pooled n=  29 mean=+2.101 sd=10.92 t=+1.04 hit=51.7 | btc_ n=  5 m=-3.90 t=-2.00 | eth_ n=  6 m=-2.06 t=-0.64 | xrp_ n=  7 m=+5.71 t=+1.16 | ltc_ n=  5 m=-2.83 t=-0.83 | doge n=  6 m=+11.17 t=+2.28
z168<-1.5 H24                pooled n= 300 mean=+0.230 sd=5.21 t=+0.77 hit=53.0 | btc_ n= 57 m=-0.28 t=-0.58 | eth_ n= 71 m=+0.46 t=+0.78 | xrp_ n= 50 m=+0.52 t=+0.74 | ltc_ n= 55 m=+0.15 t=+0.23 | doge n= 67 m=+0.28 t=+0.33
z168<-1.5 H48                pooled n= 196 mean=+0.436 sd=5.28 t=+1.16 hit=53.6 | btc_ n= 36 m=+0.01 t=+0.02 | eth_ n= 48 m=+0.54 t=+0.93 | xrp_ n= 34 m=+0.88 t=+0.96 | ltc_ n= 35 m=+0.70 t=+0.62 | doge n= 43 m=+0.11 t=+0.11
z168<-1.5 H72                pooled n= 165 mean=+1.017 sd=7.28 t=+1.80 hit=57.6 | btc_ n= 31 m=+0.42 t=+0.38 | eth_ n= 40 m=+0.91 t=+0.91 | xrp_ n= 27 m=+0.71 t=+0.59 | ltc_ n= 29 m=+2.31 t=+1.43 | doge n= 38 m=+0.84 t=+0.60
z168<-2.0 H24                pooled n= 107 mean=+0.445 sd=5.32 t=+0.87 hit=56.1 | btc_ n= 25 m=-0.11 t=-0.19 | eth_ n= 24 m=+1.25 t=+0.93 | xrp_ n= 14 m=+1.44 t=+1.37 | ltc_ n= 21 m=-0.49 t=-0.43 | doge n= 23 m=+0.46 t=+0.33
z168<-2.0 H48                pooled n=  72 mean=+0.558 sd=5.89 t=+0.80 hit=58.3 | btc_ n= 16 m=-0.64 t=-0.62 | eth_ n= 17 m=+1.16 t=+0.83 | xrp_ n= 10 m=+2.26 t=+1.18 | ltc_ n= 14 m=+0.24 t=+0.13 | doge n= 15 m=+0.30 t=+0.18
z168<-2.0 H72                pooled n=  64 mean=+0.850 sd=7.53 t=+0.90 hit=56.2 | btc_ n= 13 m=-0.39 t=-0.26 | eth_ n= 15 m=+1.19 t=+0.72 | xrp_ n=  9 m=+3.86 t=+1.90 | ltc_ n= 13 m=+0.05 t=+0.02 | doge n= 14 m=+0.44 t=+0.18
z168<-3.0 H24                pooled n=  12 mean=+2.293 sd=4.53 t=+1.75 hit=66.7 | btc_ n=  6 m=-0.39 t=-1.76 | eth_ n=  2 m=+1.45 t=+1.33 | xrp_ n=  1 m=+14.97 t=+nan | ltc_ n=  1 m=+4.88 t=+nan | doge n=  2 m=+3.57 t=+1.90
z168<-3.0 H48                pooled n=  10 mean=+3.455 sd=6.93 t=+1.58 hit=60.0 | btc_ n=  4 m=-0.23 t=-2.41 | eth_ n=  2 m=-0.39 t=-0.13 | xrp_ n=  1 m=+20.65 t=+nan | ltc_ n=  1 m=+9.03 t=+nan | doge n=  2 m=+3.29 t=+2.45
z168<-3.0 H72                pooled n=   9 mean=+5.621 sd=14.68 t=+1.15 hit=66.7 | btc_ n=  3 m=-0.58 t=-0.95 | eth_ n=  2 m=-2.11 t=-0.43 | xrp_ n=  1 m=+43.47 t=+nan | ltc_ n=  1 m=+5.02 t=+nan | doge n=  2 m=+4.03 t=+9.96
rsi24<25/>75 H72 (対称)        pooled n= 239 mean=-1.461 sd=9.59 t=-2.36 hit=45.6 | btc_ n= 54 m=-1.77 t=-2.26 | eth_ n= 52 m=-1.66 t=-2.25 | xrp_ n= 46 m=-1.23 t=-0.70 | ltc_ n= 43 m=-0.59 t=-0.45 | doge n= 44 m=-1.94 t=-0.88
z168<-2/>2 H72 (対称)          pooled n= 177 mean=-1.590 sd=10.61 t=-1.99 hit=49.7 | btc_ n= 50 m=-1.51 t=-1.98 | eth_ n= 43 m=-0.46 t=-0.57 | xrp_ n= 29 m=-0.49 t=-0.21 | ltc_ n= 22 m=-0.24 t=-0.14 | doge n= 33 m=-5.05 t=-1.57
```

読み方
- rsi14 の族は btc/eth がマイナスで、pooled もほぼ 0。落としました。
- z72（3日 z）の族は k=1.5, 2.0 で全銘柄マイナス。k=3 は n=29〜40 で pooled プラスですが btc/eth/ltc がマイナス。反転ではなく、doge/xrp の一撃です。
- z168（週 z）の族は pooled +0.2〜+1.0%、t<2、btc はしばしばマイナス。弱い。
- 対称版2つは -1.46% と -1.59%。買われすぎを売ると負けます。
- rsi24<20 だけが、3つの H すべてで5銘柄ともプラス、t 2.9〜3.2。rsi48<25 も同じ形（n=19）。

## 3. stage 2: 選ぶ前の確認（train と、train に完全に入る y1/y2 だけ）

### 3a. 出来事の数（`s2_episodes.py`、rsi24<20 H72）

5銘柄が同じ日に崩れるので、銘柄をまたいで ±72h 以内の建玉を1つに束ねました。

```
trades=40 episodes(±72h)=20
  2022-11-21  n=1  pairs=doge  nets=+9.1  ep_mean=+9.06
  2022-12-12  n=1  pairs=doge  nets=-2.3  ep_mean=-2.28
  2023-02-09  n=1  pairs=doge  nets=+3.2  ep_mean=+3.22
  2023-03-09  n=4  pairs=btc_,eth_,doge,ltc_  nets=+4.8 +7.5 +6.1 +3.5  ep_mean=+5.47
  2023-06-05  n=2  pairs=btc_,doge  nets=+1.4 +1.2  ep_mean=+1.27
  2023-06-10  n=2  pairs=ltc_,eth_  nets=-0.7 +0.5  ep_mean=-0.11
  2023-06-14  n=1  pairs=eth_  nets=+5.8  ep_mean=+5.77
  2023-08-17  n=5  pairs=btc_,eth_,xrp_,ltc_,doge  nets=-7.4 -5.1 +2.5 -0.7 +0.9  ep_mean=-1.97
  2023-09-11  n=3  pairs=xrp_,eth_,ltc_  nets=+1.6 +4.8 +8.8  ep_mean=+5.07
  2023-10-09  n=2  pairs=doge,xrp_  nets=-2.4 -4.4  ep_mean=-3.40
  2024-01-03  n=1  pairs=ltc_  nets=-0.3  ep_mean=-0.26
  2024-04-12  n=1  pairs=xrp_  nets=-9.5  ep_mean=-9.49
  2024-06-11  n=1  pairs=eth_  nets=+0.0  ep_mean=+0.03
  2024-06-24  n=1  pairs=btc_  nets=+3.8  ep_mean=+3.82
  2024-07-05  n=3  pairs=xrp_,ltc_,doge  nets=+1.6 +4.4 +5.4  ep_mean=+3.79
  2024-08-05  n=5  pairs=eth_,btc_,xrp_,ltc_,doge  nets=-7.0 +7.7 +35.4 +14.7 +18.7  ep_mean=+13.91
  2024-08-27  n=1  pairs=eth_  nets=+2.1  ep_mean=+2.09
  2024-09-16  n=1  pairs=eth_  nets=+6.8  ep_mean=+6.81
  2025-01-27  n=3  pairs=xrp_,btc_,doge  nets=+9.3 +5.3 +7.4  ep_mean=+7.35
  2025-02-03  n=1  pairs=eth_  nets=+8.6  ep_mean=+8.61
episode-level: n=20 mean=+2.937 sd=5.24 t=+2.50 hit=70%
```

40件は20回の出来事です。2024-08-05（円キャリー巻き戻し）が1回で +13.9%（xrp +35.4%）、2023-03-09（SVB）が +5.5% です。出来事の単位では t=2.50 です。

### 3b. 年ごと（`s2_yearly.py`。y3/y4 は valid と重なるので、選ぶ前には見ていません）

```
rsi24<20 H24 y1              pooled n=  18 mean=-1.096 sd=3.09 t=-1.50 hit=50.0 | btc_ n=  4 m=-2.07 t=-0.99 | eth_ n=  4 m=-1.31 t=-0.80 | xrp_ n=  1 m=-3.75 t=+nan | ltc_ n=  3 m=-3.34 t=-2.69 | doge n=  6 m=+1.26 t=+2.31
rsi24<20 H24 y2              pooled n=  19 mean=+4.804 sd=5.69 t=+3.68 hit=78.9 | btc_ n=  2 m=+4.56 t=+11.74 | eth_ n=  4 m=+1.96 t=+2.88 | xrp_ n=  6 m=+4.12 t=+1.60 | ltc_ n=  4 m=+5.74 t=+1.79 | doge n=  3 m=+8.87 t=+1.68
rsi24<20 H48 y1              pooled n=  17 mean=+0.234 sd=3.81 t=+0.25 hit=58.8 | btc_ n=  3 m=-1.78 t=-0.67 | eth_ n=  4 m=+0.85 t=+0.40 | xrp_ n=  1 m=-1.21 t=+nan | ltc_ n=  3 m=-3.35 t=-8.08 | doge n=  6 m=+2.86 t=+2.51
rsi24<20 H48 y2              pooled n=  18 mean=+5.155 sd=7.70 t=+2.84 hit=72.2 | btc_ n=  2 m=+6.42 t=+1.96 | eth_ n=  4 m=+0.17 t=+0.12 | xrp_ n=  5 m=+2.74 t=+0.63 | ltc_ n=  4 m=+8.17 t=+2.54 | doge n=  3 m=+10.97 t=+1.92
rsi24<20 H72 y1              pooled n=  17 mean=+1.771 sd=4.32 t=+1.69 hit=70.6 | btc_ n=  3 m=-0.43 t=-0.12 | eth_ n=  4 m=+2.18 t=+0.77 | xrp_ n=  1 m=+2.47 t=+nan | ltc_ n=  3 m=+0.68 t=+0.49 | doge n=  6 m=+3.03 t=+1.83
rsi24<20 H72 y2              pooled n=  18 mean=+4.749 sd=10.33 t=+1.95 hit=72.2 | btc_ n=  2 m=+5.74 t=+2.99 | eth_ n=  4 m=-0.04 t=-0.01 | xrp_ n=  5 m=+4.95 t=+0.63 | ltc_ n=  4 m=+6.92 t=+2.16 | doge n=  3 m=+7.24 t=+1.17
rsi48<25 H24 y1              pooled n=   9 mean=-2.419 sd=2.98 t=-2.44 hit=22.2 | btc_ n=  2 m=-4.41 t=-2.21 | eth_ n=  2 m=-3.10 t=-2.73 | xrp_ n=  1 m=-3.75 t=+nan | ltc_ n=  2 m=-3.48 t=-2.14 | doge n=  2 m=+1.98 t=+1.47
rsi48<25 H24 y2              pooled n=   9 mean=+7.865 sd=5.51 t=+4.29 hit=100.0 | btc_ n=  1 m=+8.27 t=+nan | eth_ n=  2 m=+2.07 t=+1.21 | xrp_ n=  2 m=+5.97 t=+5.68 | ltc_ n=  2 m=+9.80 t=+1.99 | doge n=  2 m=+13.42 t=+2.92
rsi48<25 H48 y1              pooled n=   9 mean=-1.326 sd=2.76 t=-1.44 hit=44.4 | btc_ n=  2 m=-3.18 t=-1.00 | eth_ n=  2 m=-0.71 t=-0.27 | xrp_ n=  1 m=-1.21 t=+nan | ltc_ n=  2 m=-2.82 t=-15.11 | doge n=  2 m=+1.35 t=+2.47
rsi48<25 H48 y2              pooled n=   9 mean=+9.949 sd=6.46 t=+4.62 hit=88.9 | btc_ n=  1 m=+10.85 t=+nan | eth_ n=  2 m=+0.38 t=+0.10 | xrp_ n=  2 m=+9.33 t=+39.45 | ltc_ n=  2 m=+12.96 t=+5.74 | doge n=  2 m=+16.68 t=+19.11
rsi48<25 H72 y1              pooled n=   9 mean=+1.501 sd=4.21 t=+1.07 hit=66.7 | btc_ n=  2 m=-0.56 t=-0.11 | eth_ n=  2 m=+2.53 t=+0.51 | xrp_ n=  1 m=+2.47 t=+nan | ltc_ n=  2 m=+2.52 t=+0.78 | doge n=  2 m=+1.02 t=+7.05
rsi48<25 H72 y2              pooled n=   9 mean=+7.163 sd=7.52 t=+2.86 hit=88.9 | btc_ n=  1 m=+10.35 t=+nan | eth_ n=  2 m=-0.23 t=-0.03 | xrp_ n=  2 m=+5.64 t=+1.38 | ltc_ n=  2 m=+9.57 t=+1.85 | doge n=  2 m=+12.08 t=+1.81
```

y1（FTX の年）は H24 で -1.10%、H72 で +1.77%。y2 は3つの H とも +4.7〜+5.2%。H が長いほど y1 で持ちこたえるので H=72 にしました。サイトの既定も72時間です。

### 3c. fill と hold_through（`s2_fill.py`）

```
rsi24<20 H48 next_open ht=0  pooled n=  40 mean=+3.159 sd=6.27 t=+3.19 hit=70.0 | btc_ n=  6 m=+1.84 t=+0.83 | eth_ n= 10 m=+1.34 t=+1.18 | xrp_ n=  7 m=+3.18 t=+0.99 | ltc_ n=  7 m=+3.23 t=+1.12 | doge n= 10 m=+5.70 t=+2.82 | missed=0 rolls=0 avg_h=48
rsi24<20 H48 next_open ht=1  pooled n=  40 mean=+3.159 sd=6.27 t=+3.19 hit=70.0 | btc_ n=  6 m=+1.84 t=+0.83 | eth_ n= 10 m=+1.34 t=+1.18 | xrp_ n=  7 m=+3.18 t=+0.99 | ltc_ n=  7 m=+3.23 t=+1.12 | doge n= 10 m=+5.70 t=+2.82 | missed=0 rolls=0 avg_h=48
rsi24<20 H48 limit ht=0      pooled n=  38 mean=+3.430 sd=6.45 t=+3.28 hit=73.7 | btc_ n=  6 m=+2.02 t=+0.91 | eth_ n=  9 m=+1.67 t=+1.31 | xrp_ n=  7 m=+3.51 t=+1.08 | ltc_ n=  7 m=+3.50 t=+1.23 | doge n=  9 m=+6.02 t=+2.58 | missed=4 rolls=0 avg_h=48
rsi24<20 H48 limit ht=1      pooled n=  38 mean=+3.430 sd=6.45 t=+3.28 hit=73.7 | btc_ n=  6 m=+2.02 t=+0.91 | eth_ n=  9 m=+1.67 t=+1.31 | xrp_ n=  7 m=+3.51 t=+1.08 | ltc_ n=  7 m=+3.50 t=+1.23 | doge n=  9 m=+6.02 t=+2.58 | missed=4 rolls=0 avg_h=48
rsi24<20 H72 next_open ht=0  pooled n=  40 mean=+3.827 sd=7.64 t=+3.17 hit=75.0 | btc_ n=  6 m=+2.59 t=+1.19 | eth_ n= 10 m=+2.40 t=+1.42 | xrp_ n=  7 m=+5.22 t=+0.95 | ltc_ n=  7 m=+4.24 t=+1.94 | doge n= 10 m=+4.73 t=+2.38 | missed=0 rolls=0 avg_h=72
rsi24<20 H72 next_open ht=1  pooled n=  40 mean=+3.827 sd=7.64 t=+3.17 hit=75.0 | btc_ n=  6 m=+2.59 t=+1.19 | eth_ n= 10 m=+2.40 t=+1.42 | xrp_ n=  7 m=+5.22 t=+0.95 | ltc_ n=  7 m=+4.24 t=+1.94 | doge n= 10 m=+4.73 t=+2.38 | missed=0 rolls=0 avg_h=72
rsi24<20 H72 limit ht=0      pooled n=  38 mean=+3.989 sd=7.86 t=+3.13 hit=71.1 | btc_ n=  6 m=+2.82 t=+1.31 | eth_ n=  9 m=+2.02 t=+1.11 | xrp_ n=  7 m=+5.55 t=+1.01 | ltc_ n=  7 m=+4.51 t=+2.04 | doge n=  9 m=+5.12 t=+2.31 | missed=4 rolls=0 avg_h=72
rsi24<20 H72 limit ht=1      pooled n=  38 mean=+3.989 sd=7.86 t=+3.13 hit=71.1 | btc_ n=  6 m=+2.82 t=+1.31 | eth_ n=  9 m=+2.02 t=+1.11 | xrp_ n=  7 m=+5.55 t=+1.01 | ltc_ n=  7 m=+4.51 t=+2.04 | doge n=  9 m=+5.12 t=+2.31 | missed=4 rolls=0 avg_h=72
```

limit は next_open より +0.16% よいだけで、建てそこないが 42 件中 4 件。逆張りは指値と相性がよいはずでしたが、差はほぼ出ません。保守的な next_open を採ります。
hold_through は1回も効きません。72時間後に RSI<20 が続くことがないからです。

### 3d. 閾値と期間の感度（`s2_sens.py`。変種として 5 個数えます）

```
rsi24<18 H72                 pooled n=  27 mean=+2.897 sd=5.82 t=+2.59 hit=74.1 | btc_ n=  5 m=+4.37 t=+1.40 | eth_ n=  8 m=+2.85 t=+1.45 | xrp_ n=  5 m=+1.28 t=+0.41 | ltc_ n=  4 m=+4.76 t=+1.36 | doge n=  5 m=+1.63 t=+0.82
rsi24<22 H72                 pooled n=  59 mean=+1.340 sd=7.14 t=+1.44 hit=54.2 | btc_ n=  9 m=-0.17 t=-0.10 | eth_ n= 16 m=+1.02 t=+0.66 | xrp_ n=  9 m=+3.25 t=+0.86 | ltc_ n= 11 m=+0.74 t=+0.31 | doge n= 14 m=+1.93 t=+1.19
rsi20<20 H72                 pooled n=  64 mean=+0.690 sd=6.97 t=+0.79 hit=50.0 | btc_ n=  9 m=-0.76 t=-0.47 | eth_ n= 17 m=+0.55 t=+0.38 | xrp_ n= 10 m=+2.89 t=+0.86 | ltc_ n= 13 m=-0.76 t=-0.36 | doge n= 15 m=+1.50 t=+0.97
rsi30<20 H72                 pooled n=  22 mean=+3.543 sd=5.47 t=+3.04 hit=77.3 | btc_ n=  4 m=+3.69 t=+0.94 | eth_ n=  6 m=+2.59 t=+1.04 | xrp_ n=  4 m=+4.17 t=+2.23 | ltc_ n=  4 m=+5.08 t=+1.50 | doge n=  4 m=+2.64 t=+1.21
rsi36<20 H72                 pooled n=   9 mean=+2.037 sd=3.29 t=+1.86 hit=66.7 | btc_ n=  2 m=+0.78 t=+0.20 | eth_ n=  2 m=+1.44 t=+0.37 | xrp_ n=  2 m=+2.89 t=+6.77 | ltc_ n=  2 m=+1.83 t=+0.72 | doge n=  1 m=+4.44 t=+nan
```

閾値 20 は崖です。22 に広げると平均が +3.83% から +1.34% に落ち、増えた 19 件の平均は約 -3.9% です。RSI の期間は 24〜30 なら形が同じで、20 では消えます。

### 3e. drift の基準線（`drift.py`。常に買って H 時間ごとに建て直す）

train の pooled は H24 -0.14%、H48 +0.07%、H72 +0.28%（t 1.52）。ロングだけの候補はこの +0.28% を越えなければなりません。
このとき YEARLY を全部出したので、y3/y4 の drift（H72 で +0.67% と -1.27%）は選ぶ前に目に入っています。候補の y3/y4 は見ていません。

### 3f. 運の基準線（`s3_luck.py`。同じ頻度でランダムに買うだけの戦略を 300 個、train、H72）

```
seeds=300 n: mean=42.2 min=10 max=85
t: mean=+0.15 sd=1.88 p50=+0.44 p95=+2.88 p99=+3.74 max=+4.57  count(t>=3.17)=7  count(t>=2.5)=26
mean%: avg=+0.289 p95=+3.440 max=+6.302 count(mean>=3.83)=11
```

n≈42 の希な戦略では、t の分布が正規より太い（sd 1.88）です。t≧3.17 が 300 個中 7 個、平均≧3.83% が 11 個です。

## 4. 選んだもの

`candidates/reversal.py`。RSI(24)<20 で買い、ショートは出さない。H=72、fill=next_open、hold_through=False。
RSI は直近 240 本の終値から Wilder の式で計算します。全履歴で計算した stage1 の signal と 35,040 本すべてで一致しました（`s3_candidate.out`）。lookahead_check は btc/doge とも True です。

train の詳細（`s3_candidate.out`）。5銘柄 pooled n=40 mean +3.827 sd 7.641 t 3.168 hit 75.0% required 16。btc+eth pooled n=16 mean +2.471 sd 5.146 t 1.920 hit 81.25%。
最大の出来事（2024-08-05）を除くと n=35 mean +2.387 t 3.05、上位2つを除くと n=32 mean +1.921 t 2.39 hit 72%。

## 5. valid（1回だけ。`s4_valid.py`）

```
== valid
  pair     |         n |      mean |        sd |         t |  required |  hit_rate | profit_factor |    max_dd |    sharpe | avg_hours |     rolls
  btc_jpy  |         2 |     5.312 |     4.457 |     1.685 |         3 |   100.000 |       inf |     0.000 |       nan |    72.000 |         0
      的中率(毎時) 100.00% / 重ならない nan% / 判定 2 件 / 見送り 100.0%
  eth_jpy  |         4 |    -1.717 |     6.751 |    -0.509 |         - |    25.000 |     0.518 |     1.418 |    -0.620 |    72.000 |         0
      的中率(毎時) 18.18% / 重ならない nan% / 判定 11 件 / 見送り 99.9%
  xrp_jpy  |         4 |     9.770 |    10.501 |     1.861 |         5 |    75.000 |    25.065 |     0.162 |     1.605 |    72.000 |         0
      的中率(毎時) 78.57% / 重ならない nan% / 判定 14 件 / 見送り 99.8%
  ltc_jpy  |         1 |     9.966 |       nan |       nan |         - |   100.000 |       inf |     0.000 |       nan |    72.000 |         0
      的中率(毎時) 100.00% / 重ならない nan% / 判定 6 件 / 見送り 99.9%
  doge_jpy |         4 |     6.946 |    10.196 |     1.363 |         9 |    75.000 |    18.004 |     0.163 |     1.393 |    72.000 |         0
      的中率(毎時) 80.00% / 重ならない nan% / 判定 5 件 / 見送り 99.9%
  pooled   |        15 |     5.373 |     8.899 |     2.338 |        11 |    66.667 |     5.606 |         - |         - |    72.000 |         0
      平均の95%区間 [+1.231, +9.802]  P(平均>0)=0.996
== btc+eth pooled
== train
  pair     |         n |      mean |        sd |         t |  required |  hit_rate | profit_factor |    max_dd |    sharpe | avg_hours |     rolls
  pooled   |        16 |     2.471 |     5.146 |     1.920 |        17 |    81.250 |     3.022 |         - |         - |    72.000 |         0
      平均の95%区間 [-0.011, +4.855]  P(平均>0)=0.974
== valid
  pair     |         n |      mean |        sd |         t |  required |  hit_rate | profit_factor |    max_dd |    sharpe | avg_hours |     rolls
  pooled   |         6 |     0.626 |     6.671 |     0.230 |       437 |    50.000 |     1.264 |         - |         - |    72.000 |         0
      平均の95%区間 [-4.194, +5.264]  P(平均>0)=0.614
== y1
  pair     |         n |      mean |        sd |         t |  required |  hit_rate | profit_factor |    max_dd |    sharpe | avg_hours |     rolls
  pooled   |         7 |     1.064 |     5.596 |     0.503 |       107 |    71.429 |     1.596 |         - |         - |    72.000 |         0
      平均の95%区間 [-2.893, +4.740]  P(平均>0)=0.703
== y2
  pair     |         n |      mean |        sd |         t |  required |  hit_rate | profit_factor |    max_dd |    sharpe | avg_hours |     rolls
  pooled   |         6 |     1.890 |     5.076 |     0.912 |        28 |    83.333 |     2.608 |         - |         - |    72.000 |         0
      平均の95%区間 [-2.030, +5.110]  P(平均>0)=0.841
== y3
  pair     |         n |      mean |        sd |         t |  required |  hit_rate | profit_factor |    max_dd |    sharpe | avg_hours |     rolls
  pooled   |         4 |     7.030 |     1.360 |    10.340 |         1 |   100.000 |       inf |         - |         - |    72.000 |         0
== y4
  pair     |         n |      mean |        sd |         t |  required |  hit_rate | profit_factor |    max_dd |    sharpe | avg_hours |     rolls
  pooled   |         5 |    -0.722 |     6.479 |    -0.249 |         - |    40.000 |     0.746 |         - |         - |    72.000 |         0
      平均の95%区間 [-5.529, +4.020]  P(平均>0)=0.378

== valid trades
  btc_jpy   2025-12-01 05Z  gross=+8.80 net=+8.46
  btc_jpy   2026-01-25 23Z  gross=+2.50 net=+2.16
  eth_jpy   2025-04-06 23Z  gross=+7.71 net=+7.37
  eth_jpy   2025-09-22 07Z  gross=-4.30 net=-4.64
  eth_jpy   2026-01-21 00Z  gross=-0.81 net=-1.15
  eth_jpy   2026-01-31 18Z  gross=-8.11 net=-8.45
  xrp_jpy   2025-04-07 07Z  gross=+22.20 net=+21.86
  xrp_jpy   2025-10-10 21Z  gross=+4.54 net=+4.20
  xrp_jpy   2025-12-15 18Z  gross=-1.28 net=-1.62
  xrp_jpy   2026-02-05 18Z  gross=+14.98 net=+14.64
  ltc_jpy   2025-04-06 21Z  gross=+10.31 net=+9.97
  doge_jpy  2025-04-07 07Z  gross=+21.21 net=+20.87
  doge_jpy  2025-09-22 08Z  gross=-1.29 net=-1.63
  doge_jpy  2025-10-10 23Z  gross=+8.49 net=+8.15
  doge_jpy  2026-01-19 01Z  gross=+0.74 net=+0.40

valid trades=15 episodes=9
  2025-04-06 n=4 pairs=ltc_,eth_,xrp_,doge ep_mean=+15.02
  2025-09-22 n=2 pairs=eth_,doge ep_mean=-3.13
  2025-10-10 n=2 pairs=xrp_,doge ep_mean=+6.18
  2025-12-01 n=1 pairs=btc_ ep_mean=+8.46
  2025-12-15 n=1 pairs=xrp_ ep_mean=-1.62
  2026-01-19 n=2 pairs=doge,eth_ ep_mean=-0.37
  2026-01-25 n=1 pairs=btc_ ep_mean=+2.16
  2026-01-31 n=1 pairs=eth_ ep_mean=-8.45
  2026-02-05 n=1 pairs=xrp_ ep_mean=+14.64
episode-level: n=9 mean=+3.653 sd=8.05 t=+1.36 hit=56%
drop biggest episode (2025-04-06): trade-level n=11 mean=+1.865 sd=6.60 t=+0.94
```

年ごと（5銘柄 pooled、同じ実行）。y1 n=17 mean +1.771 t 1.690。y2 n=18 mean +4.749 t 1.950。y3 n=9 mean +10.839 t 5.306。y4 n=11 mean +1.866 t 0.937。
btc+eth pooled。y1 t 0.503、y2 t 0.912、y3 t 10.34（n=4）、y4 t -0.249（n=5、mean -0.722）。

読み方
- valid の pooled は +5.37%、t 2.34 で、運で選んだ最良（+0.004%）は明確に上回ります。
- ただし利益は xrp/ltc/doge に偏り、2025-04-06（関税ショック）の1回が4件で平均 +15.0% です。それを除くと +1.87%、t 0.94 です。
- btc と eth だけでは n=6、+0.63%、t 0.23。eth は valid で 4 件中 3 件負け（-1.72%）。
- 出来事の単位では n=9、t 1.36 です。

## 6. 試した数

- harness で train を評価した戦略の変種: **52**（stage1 47 ＋ 感度 5）。
- 選んだ signal の fill/hold_through/H の組み合わせ: 8 回（同じ signal）。
- 基準線: 常に買い 3 回（H ごと）、ランダム買い 300 seed。
- valid を見た回数: **1**（5銘柄と btc+eth を同じスクリプトで出しました。y3/y4 もこの1回に含みます）。
- 診断 diag1.py は戦略ではなく、条件付き平均の表です。

## 7. 実装の要点

- 要る足は直近 240 本（10 日）。RSI(24) の Wilder 平滑は最初の 24 本の差で種を作り、以後 (au*23+up)/24。240 本あれば種の影響は (23/24)^215 ≈ 1e-4 です。
- 計算は 240 回の引き算と割り算だけ。純 Python で数ミリ秒です。
- RSI<20 なら up、それ以外は見送り。down は出しません。ロングだけなので建玉管理料は掛かりません。
- 手仕舞いは 72 時間後に成行。run.py の現在の「最後に閉じた足の終値で建てる」前提より、ここの数字（next_open）は保守的です。
- 発火は 1 銘柄あたり全時間の 0.1〜0.2%。btc+eth 合わせて年 6 件ほどです。

## 8. 危険

1. 件数。train 40 件は 20 回の出来事、valid 15 件は 9 回の出来事です。出来事の単位の t は train 2.50、valid 1.36 です。
2. btc/eth 単独では優位が見えません（train t 1.92、valid t 0.23）。valid の利益は xrp/ltc/doge と 1 回の出来事に寄っています。
3. 52 変種の後の train t 3.17 は、同じ頻度のランダム買いの上位 2.3% です。運と区別できていません。
4. 閾値 20 は崖です。22 で半減します。過剰適合の形です。
5. 買い一方です。崩れが続く相場（y1 の H24 は -1.10%）では負けます。1 件の最大損失は -9.5%（xrp 2024-04-12）と -8.45%（eth 2026-01-31）です。
6. サイトの記録として。毎時の判定は 99.8% が見送りになり、記録は年に数件しか増えません。「現実的な件数で偶然と区別する」には、btc+eth だけなら valid の required が 437 件で、届きません。
