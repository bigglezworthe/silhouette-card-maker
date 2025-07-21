---
title: 'Silhouette Card Maker'
cascade:
  type: docs
---

<!-- !TODO: YouTube video -->

![](/images/display.jpg)

Ever wanted to make your own custom card game but without the hassle of a craft knife, a rotary cutter, or a paper guillotine? How about making your own proxies to playtest your favorite TCG?

You can do it all with the press of a button and a cutting machine! And I can show you how!

If this is your first time here, check out the [tutorial](https://alan-cha.github.io/silhouette-card-maker-testing/)! Please join our [Discord server](https://discord.gg/jhsKmAgbXc) too!

## Demo

Watch me cut **104 cards in 26 minutes** without breaking a sweat!

{{< youtube RVHtqsRW8t8 >}}

## Purpose

The purpose of this repo is to enable you to use a Silhouette cutting machine to create card games and proxies. Proxies are only intended to be used for casual play and playtesting.

Proxies should be easily identifiable as proxies. You may not use this repo to create counterfeit cards to decieve people or to play in sanctioned tournaments. You are only permitted to sell cards if you are the full privileged copyright holder.

## Contents

* [code repository](https://github.com/Alan-Cha/silhouette-card-maker-testing)
* [tutorial]({{% ref "tutorial/" %}})
* [supply list]({{% ref "tutorial/supplies.md" %}})
* [create_pdf.py]({{% ref "docs/create.md" %}}), a script for laying out your cards in a PDF
* [offset_pdy.py]({{% ref "docs/offset.md" %}}), a script for adding an offset to your PDF
* [cutting_templates/](https://github.com/Alan-Cha/silhouette-card-maker-testing/tree/main/cutting_templates), a directory containing Silhoutte Studio cutting templates
* [calibration/](https://github.com/Alan-Cha/silhouette-card-maker-testing/tree/main/calibration), a directory containing offset calibration sheets
* [examples/](https://github.com/Alan-Cha/silhouette-card-maker-testing/tree/main/examples), a directory containing sample games
* [plugins/]({{% ref "plugins/" %}}), a directory containing scripts for streamlining card image acquisition


## Supported Sizes

This project supports the following card and paper sizes, with more in the future:

| Paper size | `standard`* | `japanese`** | `poker` | `poker_half` | `bridge` | `bridge_square` | `domino` | `domino_square` |
| ---------- | ----------- | ------------ | ------- | ------------ | -------- | --------------- | -------- | --------------- |
| `letter`   | ✅          | ✅          | ✅      |  ✅         | ✅       | ✅             | ✅       | ✅             |
| `tabloid`  | ✅          | ❌          | ❌      |  ❌         | ❌       | ❌             | ❌       | ❌             |
| `a4`       | ✅          | ✅          | ✅      |  ✅         | ✅       | ❌             | ❌       | ❌             |
| `a3`       | ✅          | ❌          | ❌      |  ❌         | ❌       | ❌             | ❌       | ❌             |
| `archb`    | ✅          | ❌          | ❌      |  ❌         | ❌       | ❌             | ❌       | ❌             |

| Paper size | Inches       | Millimeters   |
| ---------- | ------------ | ------------- |
| `letter`   | **8.5 x 11** | 215.9 x 279.4 |
| `tabloid`  | **11 x 17**  | 279.4 x 431.8 |
| `a4`       | 8.3 x 11.7   | **210 x 297** |
| `a3`       | 11.7 x 16.5  | **297 x 420** |
| `archb`    | **12 x 18**  | 304.8 x 457.2 |

| Card size       | Inches          | Millimeters   |
| --------------- | --------------- | ------------- |
| `standard`*     | 2.48 x 3.46     | **63 x 88**   |
| `japanese`**    | 2.32 x 3.39     | **59 x 86**   |
| `poker`         | **2.5 x 3.5**   | 63.5 x 88.9   |
| `poker_half`    | **1.75 x 2.45** | 44.45 x 62.23 |
| `bridge`        | **2.25 x 3.5**  | 57.15 x 88.9  |
| `bridge_square` | **2.25 x 2.25** | 57.15 x 57.15 |
| `domino`        | **1.75 x 3.5**  | 44.45 x 88.9  |
| `domino_square` | **1.75 x 1.75** | 44.45 x 44.45 |

\* including: **Magic the Gathering**, **Pokémon**, **Lorcana**, **One Piece**, **Digimon**, **Star Wars: Unlimited**, and **Flesh and Blood**.

** including: **Yu-Gi-Oh!**.