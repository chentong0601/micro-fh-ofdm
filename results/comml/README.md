# v2.0 R&R Experiment Outputs

## Directory map

```
results/comml/
├── stats/                    # v1.0 core experiment (DO NOT OVERWRITE)
│   ├── structural_summary.csv
│   ├── coded_summary.csv
│   └── run_manifest.json
├── stats_9dB/                # v1.0 SNR sensitivity (DO NOT OVERWRITE)
├── stats_jsr10dB/            # v1.0 JSR sensitivity (DO NOT OVERWRITE)
├── feedback_robustness/      # v1.0 feedback robustness (DO NOT OVERWRITE)
├── bound_validation/         # v2.0 theoretical bound validation (NEW)
│   ├── cd_validation.csv
│   ├── rcand_validation.csv
│   └── run_manifest.json
├── rl_baselines/             # v2.0 expanded RL comparison matrix (NEW)
│   ├── summary.csv
│   └── run_manifest.json
└── deterministic_construction/ # v2.0 wide-gap adaptation (NEW, optional)
    ├── summary.csv
    └── run_manifest.json
```

## Rule

- v1.0 outputs MUST NOT be overwritten by v2.0 experiments
- v2.0 experiments write ONLY to `results/comml/<experiment_name>/`
- Each experiment writes its own `run_manifest.json` with source hashes
- Smoke runs go to `tmp/`, never to `results/`
