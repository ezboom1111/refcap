# tshirt clean-VO accuracy triangulation (no verbatim human GT; cross-vendor agreement)

Char counts (normalized): google=413, medium=414, large-v3=396, large-v3+prompt=416

## pairwise CER (lower = more agreement). acc = 1 - CER
| ref \ hyp | google | medium | large-v3 | large-v3+prompt |
|---|---|---|---|---|
| **google** | - | 0.056 (94.4%) | 0.082 (91.8%) | 0.036 (96.4%) |
| **medium** | 0.056 (94.4%) | - | 0.075 (92.5%) | 0.051 (94.9%) |
| **large-v3** | 0.086 (91.4%) | 0.078 (92.2%) | - | 0.061 (93.9%) |
| **large-v3+prompt** | 0.036 (96.4%) | 0.050 (95.0%) | 0.058 (94.2%) | - |

## headline: cross-vendor / cross-model symmetric agreement
- large-v3 <-> google: CER=0.084  => **91.6% agreement**
- large-v3+prompt <-> google: CER=0.036  => **96.4% agreement**
- medium <-> google: CER=0.056  => **94.4% agreement**
- large-v3 <-> large-v3+prompt: CER=0.059  => **94.1% agreement**
- large-v3 <-> medium: CER=0.077  => **92.3% agreement**
