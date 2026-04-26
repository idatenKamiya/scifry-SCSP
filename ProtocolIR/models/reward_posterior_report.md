# Bayesian IRL Reward Posterior

- Inference method: MAP + Laplace
- Pairwise preferences: 838092
- Total possible preferences: 838092
- Chains: 4
- Draws per chain: 1000
- Warmup per chain: 500
- Posterior samples: 4000
- Acceptance rate: 1.000
- Diagnostic status: PASS
- Max R-hat: 1.001
- Min ESS: 3357.9
- Prior: monotonic safety-constrained Bayesian preference model
- Removed collinear learned features: total_violations, transfer_count

| Feature | MAP | Posterior Mean | 95% Credible Interval | P(weight > 0) | R-hat | ESS |
|---|---:|---:|---:|---:|---:|---:|
| contamination_violations | -121843.677 | -121882.212 | [-125503.610, -118126.283] | 0.000 | 1.000 | 3720.8 |
| pipette_range_violations | -65207.846 | -65225.386 | [-66920.191, -63470.255] | 0.000 | 1.000 | 3732.8 |
| well_overflow_violations | -49970.895 | -49984.593 | [-51354.047, -48556.075] | 0.000 | 1.000 | 3768.1 |
| aspirate_no_tip_violations | -54426.585 | -54442.629 | [-56035.646, -52824.333] | 0.000 | 1.000 | 3782.2 |
| dispense_no_tip_violations | -54720.275 | -54734.731 | [-56271.148, -53132.801] | 0.000 | 1.000 | 3755.5 |
| mix_no_tip_violations | -25000.000 | -25221.661 | [-47024.264, -3643.056] | 0.000 | 1.001 | 3929.7 |
| unknown_location_violations | -30901.163 | -30878.957 | [-35651.344, -26099.967] | 0.000 | 1.000 | 3555.0 |
| invalid_location_violations | -32030.264 | -31995.007 | [-36280.384, -27757.300] | 0.000 | 1.000 | 3995.2 |
| drop_tip_with_liquid_violations | -50000.000 | -49945.218 | [-92989.463, -6868.783] | 0.000 | 1.001 | 4000.0 |
| missing_mix_events | -470.431 | -470.486 | [-514.166, -426.328] | 0.000 | 1.000 | 4000.0 |
| tip_changes | -0.012 | -0.012 | [-0.013, -0.011] | 0.000 | 1.000 | 3971.7 |
| aspirate_events | 39.150 | 39.192 | [31.869, 46.410] | 1.000 | 1.000 | 4000.0 |
| dispense_events | 39.149 | 39.060 | [31.616, 46.689] | 1.000 | 1.000 | 3701.8 |
| mix_events | 499.868 | 499.888 | [485.318, 514.540] | 1.000 | 1.000 | 4000.0 |
| total_operations | -0.001 | -0.001 | [-0.001, -0.001] | 0.000 | 1.000 | 3357.9 |
| tip_changed_between_different_reagents | 1447.465 | 1447.563 | [1418.128, 1477.553] | 1.000 | 1.000 | 3910.4 |
| complete_transfer_pairs | 529.143 | 529.229 | [506.438, 551.966] | 1.000 | 1.000 | 4000.0 |
